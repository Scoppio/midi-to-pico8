"""The Lua lexer."""

import re

from .. import util


__all__ = [
    'LexerError',
    'Token',
    'TokSpace',
    'TokNewline',
    'TokComment',
    'TokString',
    'TokNumber',
    'TokName',
    'TokLabel',
    'TokKeyword',
    'TokSymbol',
    'Lexer',
    'LUA_KEYWORDS'
]

LUA_KEYWORDS = {
    'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
    'function', 'goto', 'if', 'in', 'local', 'nil', 'not', 'or', 'repeat',
    'return', 'then', 'true', 'until', 'while'
}


class LexerError(util.InvalidP8DataError):
    """A lexer error."""
    def __init__(self, msg, lineno, charno):
        self.msg = msg
        self.lineno = lineno
        self.charno = charno
        
    def __str__(self):
        return '{} at line {} char {}'.format(
            self.msg, self.lineno, self.charno)


class Token():
    """A base class for all tokens."""
    
    def __init__(self, data, lineno=None, charno=None):
        """Initializer.
        
        Args:
          data: The code data for the token.
          lineno: The source file line number of the first character.
          charno: The character number on the line of the first character.
        """
        self._data = data
        self._lineno = lineno
        self._charno = charno
        
    def __len__(self):
        """The length of the code string for the token."""
        return len(self.code)
    
    def __repr__(self):
        """A textual representation for debugging."""
        return '{}<{}, line {} char {}>'.format(
            self.__class__.__name__, repr(self._data),
            self._lineno, self._charno)

    def __eq__(self, other):
        """Equality operator.

        Two tokens are equal if they are of the same type and have
        equal data. Positions are insignificant.

        Args:
          other: The other Token to compare.
        """
        if (type(self) != type(other) or
            not isinstance(self, other.__class__)):
            return False
        if (isinstance(self, TokKeyword) and
            isinstance(other, TokKeyword)):
            return self._data.lower() == other._data.lower()
        return self._data == other._data
            
    def matches(self, other):
        """Matches the token against either a token class or token data.

        This is shorthand for the parser, which either wants to know
        whether the token is of a particular kind (e.g. a TokName) or
        of a particular value (a specific TokSymbol or TokKeyword).

        Args:
          other: The other Token to compare.
        """
        if isinstance(other, type):
            return isinstance(self, other)
        return self == other

    @property
    def value(self):
        """The parsed value of the token."""
        return self._data
    
    @property
    def code(self):
        """The original code of the token."""
        return self._data


class TokSpace(Token):
    """A block of whitespace, not including newlines."""
    name = 'whitespace'


class TokNewline(Token):
    """A single newline."""
    name = 'newline'


class TokComment(Token):
    """A Lua comment, including the '--' characters."""
    name = 'comment'


class TokString(Token):
    """A string literal."""
    name = 'string literal'
    def __init__(self, *args, **kwargs):
        if 'quote' in kwargs:
            self._quote = kwargs['quote']
            del kwargs['quote']
        else:
            self._quote = '"'
        super().__init__(*args, **kwargs)

    @property
    def code(self):
        escaped_chrs = []
        for c in self._data:
            if c in _STRING_REVERSE_ESCAPES:
                escaped_chrs.append('\\' + _STRING_REVERSE_ESCAPES[c])
            elif c == self._quote:
                escaped_chrs.append('\\' + c)
            else:
                escaped_chrs.append(c)
        return self._quote + ''.join(escaped_chrs) + self._quote


class TokNumber(Token):
    """A number literal.

    Negative number literals are tokenized as two tokens: a
    TokSymbol('-'), and a TokNumber(...) representing the non-negative
    number part.
    """
    name = 'number'

    # self._data is the original string representation of the number,
    # so we don't have to jump through hoops to recreate it later.
    @property
    def value(self):
        return float(self._data)
    

class TokName(Token):
    """A variable or function name."""
    name = 'name'


class TokLabel(Token):
    """A goto label."""
    name = 'label'


class TokKeyword(Token):
    """A Lua keyword."""
    name = 'keyword'


class TokSymbol(Token):
    """A Lua symbol."""
    name = 'symbol'


# A mapping of characters that can be escaped in Lua string literals using a
# "\" character, mapped to their unescaped values.
_STRING_ESCAPES = {
    '\n': '\n', 'a': '\a', 'b': '\b', 'f': '\f', 'n': '\n',
    'r': '\r', 't': '\t', 'v': '\v', '\\': '\\', '"': '"',
    "'": "'"
}
_STRING_REVERSE_ESCAPES = dict((v,k) for k,v in _STRING_ESCAPES.items())
del _STRING_REVERSE_ESCAPES["'"]
del _STRING_REVERSE_ESCAPES['"']

# A list of single-line token matching patterns and corresponding token
# classes. A token class of None causes the lexer to consume the pattern
# without emitting a token. The patterns are matched in order.
_TOKEN_MATCHERS = []
_TOKEN_MATCHERS.extend([
    (re.compile(r'--.*'), TokComment),
    (re.compile(r'[ \t]+'), TokSpace),
    (re.compile(r'\r\n'), TokNewline),
    (re.compile(r'\n'), TokNewline),
    (re.compile(r'\r'), TokNewline),
    (re.compile(r'0[xX][0-9a-fA-F]+(\.[0-9a-fA-F]+)?'), TokNumber),
    (re.compile(r'0[xX]\.[0-9a-fA-F]+'), TokNumber),
    (re.compile(r'[0-9]+(\.[0-9]+)?([eE]-?[0-9]+)?'), TokNumber),
    (re.compile(r'\.[0-9]+([eE]-?[0-9]+)?'), TokNumber),
    (re.compile(r'::[a-zA-Z_][a-zA-Z0-9_]*::'), TokLabel),
])
_TOKEN_MATCHERS.extend([
    (re.compile(r'\b'+keyword+r'\b'), TokKeyword) for keyword in LUA_KEYWORDS])
_TOKEN_MATCHERS.extend([
    (re.compile(symbol), TokSymbol) for symbol in [
    r'\+=', '-=', r'\*=', '/=', '%=',
    '==', '~=', '!=', '<=', '>=',
    r'\+', '-', r'\*', '/', '%', r'\^', '#',
    '<', '>', '=',
    r'\(', r'\)', '{', '}', r'\[', r'\]', ';', ':', ',',
    r'\.\.\.', r'\.\.', r'\.']])
_TOKEN_MATCHERS.extend([
    (re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*'), TokName)
])


class Lexer():
    """The lexer.

    A lexer object maintains state between calls to process_line() to
    manage tokens that span multiple lines.
    """
    
    def __init__(self, version):
        """Initializer.

        Args:
          version: The Pico-8 data version from the game file header.
        """
        self._version = version
        self._tokens = []
        self._cur_lineno = 0
        self._cur_charno = 0

        # If inside a string literal (else None):
        # * the pos of the start of the string
        self._in_string_lineno = None
        self._in_string_charno = None
        # * a list of chars
        self._in_string = None
        # * the starting delimiter, either " or '
        self._in_string_delim = None

    def _process_token(self, s):
        """Process a token's worth of chars from a string, if possible.

        If a token is found, it is added to self._tokens. A call might
        process characters but not emit a token.

        Args:
          s: The string to process.

        Returns:
          The number of characters processed from the beginning of the string.
        """
        i = 0

        # TODO: Pico-8 doesn't allow multiline strings, so this probably
        # shouldn't either.
        
        if self._in_string is not None:
            # Continue string literal.
            while i < len(s):
                c = s[i]

                if c == self._in_string_delim:
                    # End string literal.
                    self._tokens.append(
                        TokString(str(''.join(self._in_string)),
                                  self._in_string_lineno,
                                  self._in_string_charno,
                                  quote=self._in_string_delim))
                    self._in_string_delim = None
                    self._in_string_lineno = None
                    self._in_string_charno = None
                    self._in_string = None
                    i += 1
                    break
                
                if c == '\\':
                    # Escape character.
                    num_m = re.match(r'\d{1,3}', s[i+1:])
                    if num_m:
                        c = chr(int(num_m.group(0)))
                        i += len(num_m.group(0))
                    else:
                        next_c = s[i+1]
                        if next_c in _STRING_ESCAPES:
                            c = _STRING_ESCAPES[next_c]
                            i += 1
                            
                self._in_string.append(c)
                i += 1

        elif s.startswith("'") or s.startswith('"'):
            # Begin string literal.
            self._in_string_delim = s[0]
            self._in_string_lineno = self._cur_lineno
            self._in_string_charno = self._cur_charno
            self._in_string = []
            i = 1

        else:
            # Match one-line patterns.
            for (pat, tok_class) in _TOKEN_MATCHERS:
                m = pat.match(s)
                if m:
                    if tok_class is not None:
                        token = tok_class(m.group(0),
                                          self._cur_lineno,
                                          self._cur_charno)
                        self._tokens.append(token)
                    i = len(m.group(0))
                    break

        for c in s[:i]:
            if c == '\n':
                self._cur_lineno += 1
                self._cur_charno = 0
            else:
                self._cur_charno += 1
        return i

    def _process_line(self, line):
        """Processes a line of Lua source code.

        The line does not have to be a complete Lua statement or
        block. However, complete and valid code must have been
        processed before you can call a write_*() method.

        Args:
          line: The line of Lua source.

        Raises:
          LexerError: The line contains text that could not be mapped to known
            tokens (a syntax error).
        """
        i = 0
        while True:
            i = self._process_token(line)
            if i == 0:
                break
            line = line[i:]
        if line:
            raise LexerError('Syntax error (remaining:%r)' % (line,),
                             self._cur_lineno + 1,
                             self._cur_charno + 1)

    def process_lines(self, lines):
        """Process lines of Lua code.

        Args:
          lines: The Lua code to process, as an iterable of strings. Newline
            characters are expected to appear in the strings as they do in the
            original source, though each string in lines need not end with a
            newline.
        """
        for line in lines:
            self._process_line(line)

    @property
    def tokens(self):
        """The tokens produced by the lexer.

        This includes TokComment, TokSpace, and TokNewline
        tokens. These are not tokens of the Lua grammar, but are
        needed to reconstruct the original source with its formatting,
        or to reformat the original source while preserving comments
        and newlines.
        """
        return self._tokens
