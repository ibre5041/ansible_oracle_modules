
from .antlr3 import *
from .antlr3.tree import *
from .oraclenetservicesv3lexer import *
from .oraclenetservicesv3parser import *
import sys
import os
import getopt


class OraParameter:
    @staticmethod
    def leftestNode(elem):
        if elem.children:
            return OraParameter.leftestNode(elem.children[0])
        return elem.token

    @staticmethod
    def rightestNode(elem):
        if elem.children:
            return OraParameter.rightestNode(elem.children[-1])
        return elem.token

    def __init__(self, name):
        self.name = name

    @classmethod
    def fromNode(cls, elem):
        retval = cls(name=elem.children[0].toString())
        #
        if retval.name.upper() == "IFILE":
            raise ValueError("IFILE directive is not supported yet")
        retval.values = []
        for c in elem.children[1:]:
            if c.token.type == KEYWORD:
                retval.values.append(OraParameter.fromNode(c))
            else:
                retval.values.append(c)
        retval.lineFrom = OraParameter.leftestNode(elem).line
        retval.lineTo   = OraParameter.rightestNode(elem).line
        return retval

    @classmethod
    def fromString(cls, alias, value):
        retval = cls(name=alias)
        retval.values = []
        # Set string value (prefferably without any white spaces)
        retval.values.append(value)
        retval.lineFrom = sys.maxsize
        retval.lineTo   = sys.maxsize
        return retval

    def setvalue(self, param, value, oldvalue = None):
        changed = False
        for v in self.values:
            if not isinstance(v, OraParameter):
                continue            
            if v.name.upper() == param.upper() and len(v.values) == 1 and (oldvalue == None or str(v.values[0]) == oldvalue):
                changed = changed or v.values[0] != value
                v.values[0] = value
            changed = changed or v.setvalue(param, value, oldvalue)
        return changed

    def deleteparam(self, param):
        changed = False
        found_idx = next((i for i, v in enumerate(self.values) if isinstance(v, OraParameter) and v.name.upper() == param.upper() and len(v.values) == 1), None)
        if found_idx:
            del self.values[found_idx-1:found_idx+2]
            changed = True
        for v in self.values:
            if not isinstance(v, OraParameter):
                continue
            ch = v.deleteparam(param)
            changed = changed or ch
        return changed

    def deleteparampath(self, key):
        # Traverse lisp-like path
        path = key.split('/')
        child = self
        for i in path[0:-1]:
            # 1st find a child of desired name i
            try:
                child = next(c for c in child.values if isinstance(c, OraParameter) and c.name.upper() == i.upper())
            except StopIteration:
                raise ValueError("Child token not found: {}".format(i))

        #
        try:
            found_idx = next(i for i, c in enumerate(child.values) if isinstance(c, OraParameter) and c.name.upper() == path[-1].upper())
            del child.values[found_idx-1:found_idx+2]
            changed = True
        except StopIteration:
            pass
        return False

    def upsertparampath(self, key, value):
        changed = False
        # Traverse lisp-like path
        path = key.split('/')
        child = self
        for i in path:
            # 1st find a child of desired name i
            try:
                child = next(c for c in child.values if isinstance(c, OraParameter) and c.name.upper() == i.upper())
            except StopIteration:
                raise ValueError("Child token not found: {}".format(i))

        #
        try:
            last_child = next(c for c in child.values if isinstance(c, OraParameter) and c.name.upper() == path[-1].upper())
            changed = changed or last_child.valuesstr() != value
            last_child.values = [value]
        except StopIteration:
            changed = True
            last_child = OraParameter.fromString(path[-1], value)
            child.values.append('(')
            child.values.append(last_child)
            child.values.append(')')
        return changed

    def valuesstr(self):
        return ''.join(str(e) for e in self.values)

    
    def __str__(self):
        # Check if OraParameter instance was cleared, i.e. is targeted for removal
        if self.name:
            #return """%d-%d %s=%s""" % (self.lineFrom, self.lineTo, self.name, values)
            return """%s=%s""" % (self.name, self.valuesstr())
        else:
            return ''

        
    def __lt__(self, other):
        return self.lineFrom < other.lineFrom


class DotOraFile:
    
    def __init__(self, filename):
        self.lines = [line.rstrip() for line in open(filename)]
        #
        input = ANTLRFileStream(filename)
        lexer = OracleNetServicesV3Lexer(input);
        tokens = CommonTokenStream(lexer);
        parser = OracleNetServicesV3Parser(tokens);
        r = parser.configuration_file();
        #
        if lexer.getNumberOfSyntaxErrors():
            print >> sys.stderr, "Lexer errors: " + str(lexer.getNumberOfSyntaxErrors())
        if parser.getNumberOfSyntaxErrors():
            print >> sys.stderr, "Parser errors: " + str(parser.getNumberOfSyntaxErrors())
        #
        self.t = r.tree; # get tree from parser
        #
        self.params = []    
        for p in self.t.children:
            self.params.append(OraParameter.fromNode(p))
        self.psze = len(self.params)
        self.changed = False
        self.warn = []

    def setparamvalue(self, alias, param, value, oldvalue=None):
        for p in self.params:
            if p.name == alias or alias == "@all":
                try:
                    self.changed = self.changed or p.setvalue(param, value, oldvalue)
                except ValueError as e:
                    self.warn.append('Alias: {}, {}'.format(p, str(e)))

    def deleteparam(self, alias, param):
        for p in self.params:
            if p.name == alias or alias == "@all":
                try:
                    self.changed = self.changed or p.deleteparam(param)
                except ValueError as e:
                    self.warn.append('Alias: {}, {}'.format(p, str(e)))

    def deleteparampath(self, alias, key):
        for p in self.params:
            if p.name == alias or alias == "@all":
                try:
                    self.changed = self.changed or p.deleteparampath(key)
                except ValueError as e:
                    self.warn.append('Alias: {}, {}'.format(p, str(e)))

    def __str__(self):
        retval = ""
        lineno = 1
        params = self.params[:]
        lines  = self.lines[:]
        # Process original AST nodes/lines
        while lineno <= len(lines):
            if not params or lineno < params[0].lineFrom: 
                retval+=lines[lineno-1]
                retval+=os.linesep
            else:
                p = params.pop(0)                
                retval+=str(p)
                # Now newline after empty string
                if str(p):
                    retval+=os.linesep
                #
                lineno = p.lineTo
            lineno+=1
        # Process additionally added nodes/lines/aliases
        while params:
            p = params.pop(0)                
            retval+=str(p)                
            retval+=os.linesep            
        return retval

    def upsertalias(self, alias, value):
        try:
            param = next(p for p in self.params if p.name.upper() == alias.upper())
        except StopIteration:
            param = OraParameter.fromString(alias, value)
            self.params.append(param)
            self.changed = True
        self.changed = self.changed or param.valuesstr() != value            
        param.values = [value]

    def removealias(self, alias):
        # Find proper tns alias 1st
        try:
            param = next(p for p in self.params if p.name.upper() == alias.upper())
            param.values = []
            param.name = None
            self.changed = True
        except StopIteration:
            pass

    def getaliasatribute(self, alias, key):
        # Find proper tns alias 1st
        try:
            param = next(p for p in self.params if p.name.upper() == alias.upper())
        except StopIteration:
            raise ValueError("Alias: {} not found: {}".format(alias))

        # Traverse lisp-like path
        path = key.split('/')
        child = param
        for i in path[0:-1]:
            # 1st find a child of desired name i
            try:
                child = next(c for c in child.values if isinstance(c, OraParameter) and c.name.upper() == i.upper())
            except StopIteration:
                raise ValueError("Alias: {}, child token not found: {}".format(alias, i))

        return child
        
    def upsertaliasatribute(self, alias, key, value):
        for p in self.params:
            if p.name == alias or alias == "@all":
                try:
                    self.changed = self.changed or p.upsertparampath(key, value)
                except ValueError as e:
                    self.warn.append('Alias: {}, {}'.format(p, str(e)))



