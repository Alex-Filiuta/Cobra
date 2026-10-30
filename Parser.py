"""Однопроходный компилятор языка Cobra в байт-код стековой машины.

Токенайзера и AST нет: парсер читает исходник по символам (рекурсивный спуск)
и по ходу разбора сразу дописывает команды в self.code. Адрес перехода вперёд
в момент генерации неизвестен — на его месте остаётся None, а после разбора
блока туда вписывается настоящий адрес (backpatching).

Типы: int, string и одномерные массивы из них — int[], string[].
Массив — ссылка: "int c = a;" не копирует, а даёт второе имя тому же массиву.

Выполняет байт-код стековая машина из VM.py.
"""

import re

from VM import dump, run


IDENT_RE  = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NUMBER_RE = re.compile(r"\d+")
STRING_RE = re.compile(r'"[^"]*"')

TYPES    = {"int": 0, "string": ""}      # скалярный тип -> значение по умолчанию
KEYWORDS = {"int", "string", "if", "else", "while", "print", "resize", "len"}

# операторы языка -> команды машины; двухсимвольные сравнения стоят раньше
# односимвольных, чтобы "<=" не прочиталось как "<"
ARITH_OPS = {"+": "ADD", "-": "SUB", "*": "MUL", "/": "DIV"}
CMP_OPS   = {"==": "EQ", "!=": "NE", "<=": "LE", ">=": "GE", "<": "LT", ">": "GT"}


def is_array(type_name: str) -> bool:
    return type_name.endswith("[]")


def elem_type(type_name: str) -> str:
    return type_name[:-2]


class Parser:
    def __init__(self, src: str):
        self.src = src
        self.pos = 0
        self.code: list[tuple] = []          # байт-код: [("PUSH", 1), ("STORE", 0), ...]
        self.scopes: list[dict] = [{}]       # стек областей: имя -> (тип, номер ячейки)
        self.n_vars = 0                      # сколько ячеек памяти уже выдано

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
        for op in CMP_OPS:
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

    def ident(self) -> str:
        m = self.match_re(IDENT_RE)
        if not m:
            raise SyntaxError(f"Ожидалось имя на позиции {self.pos}")
        return m.group()

    def var_name(self) -> str:
        name = self.ident()
        if name in KEYWORDS:
            raise SyntaxError(f"'{name}' — ключевое слово, а не имя переменной")
        return name

    # ---------- генерация кода ----------

    def emit(self, *instr) -> int:
        self.code.append(instr)
        return len(self.code) - 1            # адрес команды — нужен для заплатки

    def patch(self, at: int):
        # вписать в переход по адресу at текущий адрес — конец только что разобранного куска
        self.code[at] = (self.code[at][0], len(self.code))

    # ---------- области видимости ----------

    def lookup(self, name: str) -> tuple[str, int]:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise NameError(f"Переменная '{name}' не определена")

    def declare(self, name: str, type_name: str) -> int:
        if name in self.scopes[-1]:
            raise NameError(f"Переменная '{name}' уже объявлена")
        slot = self.n_vars
        self.n_vars += 1
        self.scopes[-1][name] = (type_name, slot)
        return slot

    # ---------- запуск ----------

    def compile(self) -> list[tuple]:
        while not self.at_end():
            self.stmt()
        return self.code

    # ---------- операторы ----------

    def stmt(self):
        self.skip_ws()
        w = self.peek_word()
        if w in TYPES:
            self.var_decl()
        elif w == "if":
            self.if_stmt()
        elif w == "while":
            self.while_stmt()
        elif w == "print":
            self.print_stmt()
        elif w == "resize":
            self.resize_stmt()
        elif w is not None and w not in KEYWORDS:
            self.assign_stmt()
        else:
            raise SyntaxError(f"Ожидался оператор на позиции {self.pos}")

    def var_decl(self):
        type_name = self.ident()
        while True:
            name = self.var_name()
            if self.peek_char() == "[":                  # int a[100];
                self.eat("[")
                self.int_expr("Размер массива")
                self.eat("]")
                self.emit("NEWARR", TYPES[type_name])
                var_type = type_name + "[]"
            elif self.peek_char() == "=":
                self.pos += 1
                var_type = self.expr()
                # int b = [7, 5, 2]; — переменная становится массивом
                if var_type not in (type_name, type_name + "[]"):
                    raise TypeError(f"Нельзя присвоить {var_type} в {type_name}")
            else:
                self.emit("PUSH", TYPES[type_name])
                var_type = type_name
            # объявляем после инициализатора: в "int x = 1, y = x;" y уже видит x
            self.emit("STORE", self.declare(name, var_type))
            if self.peek_char() != ",":
                break
            self.pos += 1
        self.eat(";")

    def assign_stmt(self):
        name = self.ident()
        if self.peek_word() is not None:     # "bool b = 1;" — объявление с неизвестным типом
            raise TypeError(f"Неизвестный тип: {name}")
        type_name, slot = self.lookup(name)
        if self.peek_char() == "[":          # a[i] = ...;  на стеке: массив, индекс, значение
            self.emit("LOAD", slot)
            target_type = self.index(name, type_name)
            self.eat("=")
            self.check_assign(target_type, self.expr())
            self.emit("STOREI")
        else:
            self.eat("=")
            self.check_assign(type_name, self.expr())
            self.emit("STORE", slot)
        self.eat(";")

    def print_stmt(self):
        self.eat_word("print")
        self.expr()
        self.emit("PRINT")
        self.eat(";")

    def resize_stmt(self):
        # resize(a, n);  на стеке: массив, новый размер
        self.eat_word("resize")
        self.eat("(")
        t = self.expr()
        if not is_array(t):
            raise TypeError(f"resize: ожидался массив, а не {t}")
        self.eat(",")
        self.int_expr("Новый размер")
        self.eat(")")
        self.emit("RESIZE", TYPES[elem_type(t)])
        self.eat(";")

    def if_stmt(self):
        #       <cond>
        #       JZ  else
        #       <then>
        #       JMP end        -- только если есть else
        # else: <else>         -- блок или вложенный if (это и есть else if)
        # end:
        self.eat_word("if")
        self.int_expr("Условие")
        to_else = self.emit("JZ", None)
        self.block()
        if self.peek_word() != "else":
            self.patch(to_else)
            return
        self.eat_word("else")
        to_end = self.emit("JMP", None)
        self.patch(to_else)
        if self.peek_word() == "if":
            self.if_stmt()
        else:
            self.block()
        self.patch(to_end)

    def while_stmt(self):
        # start: <cond>
        #        JZ  end
        #        <body>
        #        JMP start
        # end:
        self.eat_word("while")
        start = len(self.code)
        self.int_expr("Условие")
        to_end = self.emit("JZ", None)
        self.block()
        self.emit("JMP", start)
        self.patch(to_end)

    # ---------- блоки ----------

    def block(self):
        self.eat("{")
        self.scopes.append({})
        while self.peek_char() not in ("}", ""):
            self.stmt()
        self.eat("}")
        self.scopes.pop()

    # ---------- выражения ----------
    # каждый метод генерирует код, который оставляет значение на стеке,
    # и возвращает тип этого значения: "int", "string", "int[]" или "string[]"

    def int_expr(self, what: str):
        if (t := self.expr()) != "int":
            raise TypeError(f"{what}: ожидался int, а не {t}")

    def index(self, name: str, type_name: str) -> str:
        """'[выражение]' после имени массива: оставляет индекс на стеке, возвращает тип элемента."""
        if not is_array(type_name):
            raise TypeError(f"'{name}' — не массив, а {type_name}")
        self.eat("[")
        self.int_expr("Индекс")
        self.eat("]")
        return elem_type(type_name)

    def expr(self) -> str:
        left = self.additive()
        op = self.peek_op()
        if op is None:
            return left
        self.pos += len(op)
        right = self.additive()
        if left != right or is_array(left):
            raise TypeError(f"Нельзя сравнивать {left} и {right}")
        self.emit(CMP_OPS[op])
        return "int"                         # сравнение даёт 1 или 0

    def additive(self) -> str:
        left = self.multiplicative()
        while (op := self.peek_char()) in ("+", "-"):
            self.pos += 1
            right = self.multiplicative()
            # складывать можно int и string, вычитать — только int
            if not (left == right == "int" or left == right == "string" and op == "+"):
                raise TypeError(f"Операция {op!r} не применима к {left} и {right}")
            self.emit(ARITH_OPS[op])
        return left

    def multiplicative(self) -> str:
        left = self.unary()
        while (op := self.peek_char()) in ("*", "/"):
            self.pos += 1
            right = self.unary()
            if left != "int" or right != "int":
                raise TypeError(f"Операция {op!r} не применима к {left} и {right}")
            self.emit(ARITH_OPS[op])
        return left

    def unary(self) -> str:
        if self.peek_char() == "-":
            self.pos += 1
            if (t := self.unary()) != "int":
                raise TypeError(f"Унарный минус не применим к {t}")
            self.emit("NEG")
            return t
        return self.primary()

    def primary(self) -> str:
        if self.peek_char() == "(":
            self.pos += 1
            t = self.expr()
            self.eat(")")
            return t
        if self.peek_char() == "[":
            return self.array_literal()
        if m := self.match_re(NUMBER_RE):
            self.emit("PUSH", int(m.group()))
            return "int"
        if m := self.match_re(STRING_RE):
            self.emit("PUSH", m.group()[1:-1])
            return "string"
        if self.peek_word() == "len":
            return self.len_call()
        m = self.match_re(IDENT_RE)
        if m and m.group() not in KEYWORDS:
            name = m.group()
            type_name, slot = self.lookup(name)
            self.emit("LOAD", slot)
            if self.peek_char() == "[":      # a[i]
                type_name = self.index(name, type_name)
                self.emit("LOADI")
            return type_name
        raise SyntaxError(f"Ожидалось выражение на позиции {self.pos}")

    def len_call(self) -> str:
        # len(a) — текущий размер массива
        self.eat_word("len")
        self.eat("(")
        if not is_array(t := self.expr()):
            raise TypeError(f"len: ожидался массив, а не {t}")
        self.eat(")")
        self.emit("LEN")
        return "int"

    def array_literal(self) -> str:
        # [7, 5, 2] — элементы ложатся на стек по порядку, BUILD собирает их в массив
        self.eat("[")
        if self.peek_char() == "]":
            raise SyntaxError(f"Пустой список на позиции {self.pos}: пустой массив — это int a[0];")
        first = self.expr()
        if is_array(first):
            raise TypeError("Вложенные массивы не поддерживаются")
        count = 1
        while self.peek_char() == ",":
            self.pos += 1
            if (t := self.expr()) != first:
                raise TypeError(f"Элементы массива разных типов: {first} и {t}")
            count += 1
        self.eat("]")
        self.emit("BUILD", count)
        return first + "[]"

    # ---------- типы ----------

    @staticmethod
    def check_assign(type_name: str, value_type: str):
        if type_name != value_type:
            raise TypeError(f"Нельзя присвоить {value_type} в {type_name}")


def execute(src: str) -> dict:
    """Компилирует и выполняет программу; возвращает глобальные переменные {имя: (тип, значение)}."""
    parser = Parser(src)
    memory = run(parser.compile(), parser.n_vars)
    return {name: (t, memory[slot]) for name, (t, slot) in parser.scopes[0].items()}


if __name__ == "__main__":
    src = '''
        int x = 0;
        if x > 0 { x = 3 + x; } else if x == 0 { x = 1; } else { x = 2; }

        int a[100];
        int b = [7, 5, 2];
        resize(a, 50);
        a[0] = b[0] * b[1];
        print a[0];
        print len(a);

        int i = 3;
        while i > 0 {
            print i;
            i = i - 1;
        }
    '''
    dump(Parser(src).compile())
    print(execute(src))
