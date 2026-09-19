import re
from dataclasses import dataclass


IDENT_RE  = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NUMBER_RE = re.compile(r"\d+")
STRING_RE = re.compile(r'"[^"]*"')


@dataclass
class Procedure:
    params: list      # [(type, name), ...]
    body_start: int   # позиция сразу после '{'


class Parser:
    def __init__(self, src: str):
        self.src = src
        self.pos = 0
        self.scopes: list[dict] = [{}]           # стек областей видимости
        self.procs: dict[str, Procedure] = {}    # имя -> Procedure

    # ---------- помощники ----------

    def skip_ws(self):
        while self.pos < len(self.src) and self.src[self.pos].isspace():
            self.pos += 1

    def at_end(self) -> bool:
        self.skip_ws()
        return self.pos >= len(self.src)

    def peek_char(self) -> str:
        self.skip_ws()
        return self.src[self.pos] if self.pos < len(self.src) else ""

    def peek_word(self) -> str | None:
        save = self.pos
        m = self.match_re(IDENT_RE)
        self.pos = save
        return m.group() if m else None

    def peek_op(self) -> str | None:
        self.skip_ws()
        for op in ("==", "!=", "<=", ">=", "<", ">"):
            if self.src.startswith(op, self.pos):
                return op
        return None

    def match_re(self, regex):
        self.skip_ws()
        m = regex.match(self.src, self.pos)
        if m:
            self.pos = m.end()
        return m

    def eat(self, ch: str):
        if self.peek_char() != ch:
            raise SyntaxError(f"Ожидалось {ch!r} на позиции {self.pos}")
        self.pos += 1

    def eat_word(self, word: str):
        m = self.match_re(IDENT_RE)
        if not m or m.group() != word:
            raise SyntaxError(f"Ожидалось {word!r} на позиции {self.pos}")

    # ---------- области видимости ----------

    def lookup(self, name: str):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise NameError(f"Переменная '{name}' не определена")

    def declare(self, name: str, type_name: str, value):
        if name in self.scopes[-1]:
            raise NameError(f"Переменная '{name}' уже объявлена")
        self.scopes[-1][name] = (type_name, value)

    # ---------- запуск ----------

    def run(self):
        while not self.at_end():
            self.stmt()
        if "main" in self.procs:
            self.call_proc("main", [])

    # ---------- statements ----------

    def stmt(self):
        self.skip_ws()
        w = self.peek_word()
        if w in ("int", "string"):
            self.var_decl()
        elif w == "proc":
            self.proc_decl()
        elif w == "print":
            self.print_stmt()
        elif w == "if":
            self.if_stmt()
        elif w == "while":
            self.while_stmt()
        else:
            self.expr_stmt()

    def var_decl(self):
        type_name = self.match_re(IDENT_RE).group()
        while True:
            name = self.match_re(IDENT_RE).group()
            value = None
            if self.peek_char() == "=":
                self.pos += 1
                value = self.expr()
            if value is None:
                value = self.default_value(type_name)
            else:
                self.check_type(type_name, value)
            self.declare(name, type_name, value)
            if self.peek_char() == ",":
                self.pos += 1
                continue
            break
        self.eat(";")

    def proc_decl(self):
        self.eat_word("proc")
        name = self.match_re(IDENT_RE).group()
        self.eat("(")
        params = []
        if self.peek_char() != ")":
            while True:
                ptype = self.match_re(IDENT_RE).group()
                pname = self.match_re(IDENT_RE).group()
                params.append((ptype, pname))
                if self.peek_char() == ",":
                    self.pos += 1
                    continue
                break
        self.eat(")")
        self.eat("{")
        body_start = self.pos
        self.skip_block()          # пропускаем тело, запоминаем только позицию
        self.procs[name] = Procedure(params, body_start)

    def print_stmt(self):
        self.eat_word("print")
        value = self.expr()
        self.eat(";")
        print(value)

    def expr_stmt(self):
        self.expr()
        self.eat(";")

    def if_stmt(self):
        self.eat_word("if")
        cond = self.expr()
        self.eat("{")
        if cond:
            self.exec_block()
            if self.peek_word() == "else":
                self.eat_word("else")
                self.eat("{")
                self.skip_block()
        else:
            self.skip_block()
            if self.peek_word() == "else":
                self.eat_word("else")
                self.eat("{")
                self.exec_block()

    def while_stmt(self):
        self.eat_word("while")
        cond_start = self.pos
        cond = self.expr()
        self.eat("{")
        body_start = self.pos
        self.skip_block()
        body_end = self.pos

        while cond:
            self.pos = body_start
            self.exec_block()          # тело
            self.pos = cond_start
            cond = self.expr()         # пере-вычисляем условие
        self.pos = body_end

    # ---------- блоки ----------

    def exec_block(self):
        # '{' уже съеден; выполняем до '}' и съедаем его
        while True:
            self.skip_ws()
            if self.peek_char() == "}":
                self.pos += 1
                return
            self.stmt()

    def skip_block(self):
        # '{' уже съеден; пропускаем до парного '}'
        depth = 1
        while depth > 0:
            ch = self.src[self.pos]
            if ch == '"':                      # чтобы '}' внутри строки не считался
                self.pos += 1
                while self.pos < len(self.src) and self.src[self.pos] != '"':
                    self.pos += 1
                self.pos += 1
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
            self.pos += 1

    # ---------- вызов процедуры ----------

    def call_proc(self, name: str, args: list):
        if name not in self.procs:
            raise NameError(f"Процедура '{name}' не определена")
        proc = self.procs[name]
        if len(args) != len(proc.params):
            raise TypeError(
                f"'{name}': ожидалось {len(proc.params)} аргументов, "
                f"получено {len(args)}"
            )

        scope = {}
        for (ptype, pname), val in zip(proc.params, args):
            self.check_type(ptype, val)
            scope[pname] = (ptype, val)
        self.scopes.append(scope)

        saved = self.pos
        self.pos = proc.body_start
        try:
            self.exec_block()
        finally:
            self.pos = saved
            self.scopes.pop()
        return None

    # ---------- выражения ----------

    def expr(self):
        left = self.additive()
        op = self.peek_op()
        if op:
            self.pos += len(op)
            right = self.additive()
            return self.binop(op, left, right)
        return left

    def additive(self):
        left = self.multiplicative()
        while self.peek_char() in ("+", "-"):
            op = self.peek_char()
            self.pos += 1
            right = self.multiplicative()
            left = left + right if op == "+" else left - right
        return left

    def multiplicative(self):
        left = self.unary()
        while self.peek_char() in ("*", "/"):
            op = self.peek_char()
            self.pos += 1
            right = self.unary()
            left = left * right if op == "*" else left // right
        return left

    def unary(self):
        if self.peek_char() == "-":
            self.pos += 1
            return -self.unary()
        return self.primary()

    def primary(self):
        self.skip_ws()
        if self.peek_char() == "(":
            self.pos += 1
            v = self.expr()
            self.eat(")")
            return v
        if (m := self.match_re(NUMBER_RE)):
            return int(m.group())
        if (m := self.match_re(STRING_RE)):
            return m.group()[1:-1]
        if (m := self.match_re(IDENT_RE)):
            name = m.group()
            if self.peek_char() == "(":
                self.pos += 1
                args = []
                if self.peek_char() != ")":
                    while True:
                        args.append(self.expr())
                        if self.peek_char() == ",":
                            self.pos += 1
                            continue
                        break
                self.eat(")")
                return self.call_proc(name, args)
            _, val = self.lookup(name)
            return val
        raise SyntaxError(f"Ожидалось выражение на позиции {self.pos}")

    # ---------- типы и операторы ----------

    @staticmethod
    def default_value(type_name: str):
        if type_name == "int":
            return 0
        if type_name == "string":
            return ""
        raise TypeError(f"Неизвестный тип: {type_name}")

    @staticmethod
    def check_type(type_name: str, value):
        if type_name == "int" and not isinstance(value, int):
            raise TypeError(f"Нельзя присвоить {value!r} в int")
        if type_name == "string" and not isinstance(value, str):
            raise TypeError(f"Нельзя присвоить {value!r} в string")

    @staticmethod
    def binop(op, left, right):
        if op == "+":  return left + right
        if op == "-":  return left - right
        if op == "*":  return left * right
        if op == "/":  return left // right
        if op == "<":  return left < right
        if op == ">":  return left > right
        if op == "<=": return left <= right
        if op == ">=": return left >= right
        if op == "==": return left == right
        if op == "!=": return left != right
        raise SyntaxError(f"Неизвестный оператор: {op}")


if __name__ == "__main__":
    src = '''
        int x = 1;

        proc foo(int v){
            print (v+5) * 10;
        }

        proc main(){
            if x > 0 {
                foo(x);
            }
            else {
                while x > 0 {
                    foo(x+1);
                }
            }
        }
    '''
    Parser(src).run()