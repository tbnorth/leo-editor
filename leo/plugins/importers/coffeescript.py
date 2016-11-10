#@+leo-ver=5-thin
#@+node:ekr.20160505094722.1: * @file importers/coffeescript.py
'''The @auto importer for coffeescript.'''
import re
import leo.core.leoGlobals as g
import leo.plugins.importers.linescanner as linescanner
Importer = linescanner.Importer
#@+others
#@+node:ekr.20160505094722.2: ** class CoffeeScriptImporter(Importer)
class CoffeeScriptImporter(Importer):

    #@+others
    #@+node:ekr.20160505101118.1: *3* coffee.__init__
    def __init__(self, importCommands, atAuto):
        '''Ctor for CoffeeScriptScanner class.'''
        Importer.__init__(self,
            importCommands,
            atAuto = atAuto,
            language = 'coffeescript',
            strict = True
        )
        self.at_others = []
            # A list of postitions that have an @others directive.
        self.at_tab_width = None
            # Default, overridden later.
        self.def_name = None
        self.errors = 0
        self.root = None
        self.tab_width = self.c.tab_width or -4
            # Used to compute lws.
        
    #@+node:ekr.20161108181857.1: *3* coffee.post_pass & helpers
    def post_pass(self, parent):
        '''Massage the created nodes.'''
        trace = False and not g.unitTesting and self.root.h.endswith('1.coffee')
        if trace:
            g.trace('='*60)
            for p in parent.self_and_subtree():
                print('***** %s' % p.h)
                self.print_lines(g.splitLines(p.b))
        self.move_trailing_lines(parent)
        self.undent_nodes(parent)
        if trace:
            g.trace('-'*60)
            for p in parent.self_and_subtree():
                print('***** %s' % p.h)
                self.print_lines(g.splitLines(p.b))
    #@+node:ekr.20160505173347.1: *4* coffee.delete_trailing_lines
    def delete_trailing_lines(self, p):
        '''Delete the trailing lines of p.b and return them.'''
        body_lines, trailing_lines = [], []
        for s in g.splitLines(p.b):
            strip = s.strip()
            if not strip or strip.startswith('#'):
                trailing_lines.append(s)
            else:
                body_lines.extend(trailing_lines)
                body_lines.append(s)
                trailing_lines = []
        # Clear trailing lines if they are all blank.
        if all([not z.strip() for z in trailing_lines]):
            trailing_lines = []
        p.b = ''.join(body_lines)
        return trailing_lines
    #@+node:ekr.20160505170558.1: *4* coffee.move_trailing_lines
    def move_trailing_lines(self, parent):
        '''Move trailing lines into the following node.'''
        prev_lines = []
        last = None
        for p in parent.subtree():
            trailing_lines = self.delete_trailing_lines(p)
            if prev_lines:
                # g.trace('moving lines from', last.h, 'to', p.h)
                p.b = ''.join(prev_lines) + p.b
            prev_lines = trailing_lines
            last = p.copy()
        if prev_lines:
            # These should go after the @others lines in the parent.
            lines = g.splitLines(parent.b)
            for i, s in enumerate(lines):
                if s.strip().startswith('@others'):
                    lines = lines[:i+1] + prev_lines + lines[i+2:]
                    parent.b = ''.join(lines)
                    break
            else:
                # Fall back.
                last.b = last.b + ''.join(prev_lines)
    #@+node:ekr.20160505170639.1: *4* coffee.undent_nodes
    def undent_nodes(self, parent):
        '''Unindent all nodes in parent's tree.'''
        for p in parent.self_and_subtree():
            p.b = self.undent_coffeescript_body(p.b)
    #@+node:ekr.20160505180032.1: *4* coffee.undent_coffeescript_body
    def undent_coffeescript_body(self, s):
        '''Return the undented body of s.'''
        trace = False and not g.unitTesting and self.root.h.endswith('1.coffee')
        lines = g.splitLines(s)
        if trace:
            g.trace('='*20)
            self.print_lines(lines)
        # Undent all leading whitespace or comment lines.
        leading_lines = []
        for line in lines:
            if self.is_ws_line(line):
                # Tricky.  Stipping a black line deletes it.
                leading_lines.append(line if line.isspace() else line.lstrip())
            else:
                break
        i = len(leading_lines)
        # Don't unindent the def/class line! It prevents later undents.
        tail = self.undent_body_lines(lines[i:], ignoreComments=True)
        # Remove all blank lines from leading lines.
        if 0:
            for i, line in enumerate(leading_lines):
                if not line.isspace():
                    leading_lines = leading_lines[i:]
                    break
        result = ''.join(leading_lines) + tail
        if trace:
            g.trace('-'*20)
            self.print_lines(g.splitLines(result))
        return result


    #@+node:ekr.20160505100917.1: *3* coffee.run
    def run(self, s, parent, parse_body=False, prepass=False):
        '''The top-level code for the coffeescript scanners.'''
        # g.trace('='*40)
        c = self.c
        changed = c.isChanged()
        if prepass:
            return False, []
        # Set ivars for check()
        self.root = parent.copy()
        self.file_s = s
        self.scan(s, parent, indent=False)
        suffix = '\n@language coffeescript\n@tabwidth %s\n' % (
            self.at_tab_width or -2)
        parent.b = parent.b.rstrip() + suffix
        self.post_pass(parent)
        ok = self.errors == 0 and self.check(s, parent)
        g.app.unitTestDict['result'] = ok
        if not ok:
            parent.b += '\n@ignore\n'
        # It's always useless for an an import to dirty the outline.
        for p in parent.self_and_subtree():
            p.clearDirty()
        c.setChanged(changed)
        return ok
    #@+node:ekr.20160505100958.1: *3* coffee.scan & helpers
    def scan(self, s1, parent, indent=True, do_def=True):
        '''Create an outline from Coffeescript (.coffee) file.'''
        # pylint: disable=arguments-differ
        trace = False and not g.unitTesting and self.root.h.endswith('1.coffee')
        if not s1.strip():
            return
        lines = g.splitLines(s1)
        if trace:
            g.trace('='*40)
            self.print_lines(lines)
        i, body_lines = 0, []
        at_others = False
        while i < len(lines):
            progress = i
            s = lines[i]
            is_class = g.match_word(s, 0, 'class')
            is_def = do_def and not is_class and self.starts_def(s)
            if self.is_ws_line(s):
                body_lines.append(s)
                i += 1
            elif is_class or is_def:
                # Important: all undents are done in a later pass.
                child = parent.insertAsLastChild()
                child.h = self.class_name(s) if is_class else self.def_name
                child.b = s
                if is_class:
                    # The indentation will be the difference between s and s2
                    if i+1 < len(lines):
                        s1_level = self.get_leading_indent(lines, i, ignoreComments=False)
                        s2_level = self.get_leading_indent(lines, i+1, ignoreComments=True)
                        # g.trace('(coffeescript)', s1_level, s2_level, repr(s))
                    else:
                        self.errors += 1
                        return
                    indent = max(0, s2_level-s1_level)
                    if not self.at_tab_width:
                        self.at_tab_width = -indent
                    child.b = child.b + ' '*indent+'@others\n'
                    self.at_others.append(child.copy())
                elif not any([parent == z for z in self.at_others]):
                    self.at_others.append(parent.copy())
                    body_lines.append('@others\n\n')
                    at_others = True
                block_lines = self.skip_block(lines[i:])
                assert block_lines
                i += len(block_lines)
                s2 = ''.join(block_lines[1:])
                self.scan(s2, child, do_def=not is_def)
            elif at_others:
                # Alas, this is necessary.
                child = parent.insertAsLastChild()
                child.h = s
                child.b = s
                i += 1
            else:
                body_lines.append(s)
                i += 1
            assert progress < i
        if trace:
            g.trace('-'*40)
            self.print_lines(body_lines)
        parent.b = parent.b + ''.join(body_lines)
    #@+node:ekr.20160505114047.1: *4* coffee.class_name
    def class_name(self, s):
        '''Return the name of the class in line s.'''
        assert s.startswith('class')
        m = re.match(r'class(\s+)(\w+)',s)
        name = m.group(2) if m else '<**bad class name**>'
        return 'class ' + name
    #@+node:ekr.20160505102909.1: *4* coffee.skip_block
    def skip_block(self, lines):
        '''Return all lines of the block that starts at lines[0].'''
        trace = False and not g.unitTesting and self.root.h.endswith('1.coffee')
        assert lines
        if trace:
            g.trace('='*40, len(lines))
            self.print_lines(lines)
        block_lines = [lines[0]]
        level1 = self.get_int_lws(lines[0])
        for s in lines[1:]:
            level = self.get_int_lws(s)
            if self.is_ws_line(s) or level > level1:
                block_lines.append(s)
            else:
                break
        if trace:
            g.trace('-'*40, len(lines))
            self.print_lines(block_lines)
        return block_lines
    #@+node:ekr.20160505113917.1: *4* coffee.starts_def
    def starts_def(self, s):
        '''
        Return True if line s starts a coffeescript function.
        Sets or clears the def_name ivar.
        '''
        m = re.match('(.+):(.*)->', s) or re.match('(.+)=(.*)->', s)
        self.def_name = m.group(1).strip() if m else None
        return bool(m)
    #@-others
#@-others
importer_dict = {
    'class': CoffeeScriptImporter,
    'extensions': ['.coffee', ],
}
#@-leo
