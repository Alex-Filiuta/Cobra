"""Тесты компилятора Cobra из Parser.py. Запуск: pytest Test.py -v"""

import pytest
from Parser import Parser, execute


def compile_src(src: str) -> list[tuple]:
    return Parser(src).compile()


def values(result: dict) -> dict:
    """{name: (type, value)} -> {name: value}"""
    return {name: v for name, (_, v) in result.items()}


# ---------- Байт-код: объявления ----------

@pytest.mark.parametrize("src, expected", [
    ("int x = 1;",         [("PUSH", 1), ("STORE", 0)]),
    ("int x;",             [("PUSH", 0), ("STORE", 0)]),
    ('string c = "abc";',  [("PUSH", "abc"), ("STORE", 0)]),
    ("string s;",          [("PUSH", ""), ("STORE", 0)]),
    ("int x, y = 5;",      [("PUSH", 0), ("STORE", 0),
                            ("PUSH", 5), ("STORE", 1)]),
    ("int x = 1 + 2 * 3;", [("PUSH", 1), ("PUSH", 2), ("PUSH", 3),
                            ("MUL",), ("ADD",), ("STORE", 0)]),
])
def test_bytecode_decl(src, expected):
    assert compile_src(src) == expected


@pytest.mark.parametrize("src", [
    "int x=1;",
    "int  x  =  1 ;",
    "int\tx\t=\t1\t;",
    "  int x = 1;  ",
    "int\nx\n=\n1\n;",
])
def test_whitespace_tolerance(src):
    assert compile_src(src) == [("PUSH", 1), ("STORE", 0)]


# ---------- Байт-код: if и while ----------

def test_bytecode_if():
    assert compile_src("int x; if x > 0 { x = 1; }") == [
        ("PUSH", 0), ("STORE", 0),           # 0-1   int x;
        ("LOAD", 0), ("PUSH", 0), ("GT",),   # 2-4   x > 0
        ("JZ", 8),                           # 5     ложь -> за if
        ("PUSH", 1), ("STORE", 0),           # 6-7   x = 1;
    ]


def test_bytecode_if_else():
    assert compile_src("int x; if x > 0 { x = 1; } else { x = 2; }") == [
        ("PUSH", 0), ("STORE", 0),           # 0-1   int x;
        ("LOAD", 0), ("PUSH", 0), ("GT",),   # 2-4   x > 0
        ("JZ", 9),                           # 5     ложь -> else
        ("PUSH", 1), ("STORE", 0),           # 6-7   x = 1;
        ("JMP", 11),                         # 8     -> за else
        ("PUSH", 2), ("STORE", 0),           # 9-10  x = 2;
    ]


def test_bytecode_while():
    assert compile_src("int x = 3; while x > 0 { x = x - 1; }") == [
        ("PUSH", 3), ("STORE", 0),           # 0-1   int x = 3;
        ("LOAD", 0), ("PUSH", 0), ("GT",),   # 2-4   x > 0
        ("JZ", 11),                          # 5     ложь -> за цикл
        ("LOAD", 0), ("PUSH", 1), ("SUB",),  # 6-8   x - 1
        ("STORE", 0),                        # 9     x = ...
        ("JMP", 2),                          # 10    -> к условию
    ]


# ---------- Байт-код: массивы ----------

NEW_A = [("PUSH", 3), ("NEWARR", 0), ("STORE", 0)]       # int a[3];


@pytest.mark.parametrize("src, expected", [
    ("int a[3];",          NEW_A),
    ("string s[2];",       [("PUSH", 2), ("NEWARR", ""), ("STORE", 0)]),
    ("int b = [7, 5, 2];", [("PUSH", 7), ("PUSH", 5), ("PUSH", 2), ("BUILD", 3), ("STORE", 0)]),
    ("int a[3]; a[1] = 9;",     NEW_A + [("LOAD", 0), ("PUSH", 1), ("PUSH", 9), ("STOREI",)]),
    ("int a[3]; int x = a[1];", NEW_A + [("LOAD", 0), ("PUSH", 1), ("LOADI",), ("STORE", 1)]),
    ("int a[3]; resize(a, 5);", NEW_A + [("LOAD", 0), ("PUSH", 5), ("RESIZE", 0)]),
    ("int a[3]; int l = len(a);", NEW_A + [("LOAD", 0), ("LEN",), ("STORE", 1)]),
])
def test_bytecode_arrays(src, expected):
    assert compile_src(src) == expected


# ---------- Выполнение: объявления ----------

@pytest.mark.parametrize("src, expected", [
    ("int x = 1;",          {"x": ("int", 1)}),
    ('string c = "abc";',   {"c": ("string", "abc")}),
    ("int x=1, y=2;",       {"x": ("int", 1), "y": ("int", 2)}),
    ("int x;",              {"x": ("int", 0)}),
    ("string s;",           {"s": ("string", "")}),
    ("",                    {}),
    ("   \n  ",             {}),
    ('int x = 1; string s = "a";',
        {"x": ("int", 1), "s": ("string", "a")}),
])
def test_execute(src, expected):
    assert execute(src) == expected


@pytest.mark.parametrize("src, expected", [
    ("int a, b = 7, c;",              {"a": 0, "b": 7, "c": 0}),
    ('int x = 1; string s = "abc";',  {"x": 1, "s": "abc"}),
])
def test_execute_values(src, expected):
    assert values(execute(src)) == expected


def test_full_program():
    src = 'int x = 1; int x1, y; int a=1, b=2; string c = "abc";'
    assert execute(src) == {
        "x":  ("int", 1),
        "x1": ("int", 0),
        "y":  ("int", 0),
        "a":  ("int", 1),
        "b":  ("int", 2),
        "c":  ("string", "abc"),
    }


# ---------- Выполнение: присваивание ----------

@pytest.mark.parametrize("src, expected", [
    ("int x; x = 5;",                  {"x": 5}),
    ("int x = 2; x = 3 + x;",          {"x": 5}),
    ("int x = 7; x = x / 2;",          {"x": 3}),
    ("int x = 2; x = -x * (1 + 2);",   {"x": -6}),
    ("int x = 1, y = x + 1;",          {"x": 1, "y": 2}),
    ("int x = 2; int y = x > 1;",      {"x": 2, "y": 1}),    # сравнение даёт 1 или 0
    ('string s = "ab"; s = s + "c";',  {"s": "abc"}),
])
def test_assign(src, expected):
    assert values(execute(src)) == expected


# ---------- Выполнение: if / else if / else ----------

IF_CHAIN = "if x > 0 { x = 3 + x;} else if x == 0 {x =1;} else {x = 2;}"


@pytest.mark.parametrize("start, expected", [(5, 8), (0, 1), (-3, 2)])
def test_if_else_if_else(start, expected):
    assert values(execute(f"int x = {start}; {IF_CHAIN}")) == {"x": expected}


@pytest.mark.parametrize("start, expected", [(5, 1), (0, 0)])
def test_if_without_else(start, expected):
    src = f"int x = {start}, r; if x > 0 {{ r = 1; }}"
    assert values(execute(src))["r"] == expected


@pytest.mark.parametrize("start, expected", [
    (1, "один"), (2, "два"), (3, "три"), (9, "много"),
])
def test_long_else_if_chain(start, expected):
    src = f'''
        int x = {start}; string s;
        if x == 1 {{ s = "один"; }}
        else if x == 2 {{ s = "два"; }}
        else if x == 3 {{ s = "три"; }}
        else {{ s = "много"; }}
    '''
    assert values(execute(src))["s"] == expected


def test_nested_if():
    src = "int a = 1, b = 0, r; if a > 0 { if b > 0 { r = 1; } else { r = 2; } } else { r = 3; }"
    assert values(execute(src))["r"] == 2


def test_if_no_spaces():
    assert values(execute("int x=1;if x>0{x=5;}else{x=6;}")) == {"x": 5}


# ---------- Выполнение: while ----------

@pytest.mark.parametrize("src, expected", [
    ("int x = 3; while x > 0 { x = x - 1; }",   {"x": 0}),
    ("int x = 0; while x>0 { x = x +1;}",       {"x": 0}),   # условие ложно сразу
    ("int x = 5; while x>0{x=x-1;}",            {"x": 0}),
    ("int i = 0, s = 0; while i < 5 { i = i + 1; s = s + i; }",
        {"i": 5, "s": 15}),
])
def test_while(src, expected):
    assert values(execute(src)) == expected


def test_nested_while():
    # j объявлена в теле внешнего цикла и обнуляется на каждом проходе
    src = '''
        int i = 0, n = 0;
        while i < 3 {
            int j = 0;
            while j < 4 { n = n + 1; j = j + 1; }
            i = i + 1;
        }
    '''
    assert values(execute(src)) == {"i": 3, "n": 12}


def test_if_inside_while():
    src = '''
        int i = 0, even = 0;
        while i < 10 {
            if i == i / 2 * 2 { even = even + 1; }
            i = i + 1;
        }
    '''
    assert values(execute(src))["even"] == 5


def test_print(capsys):
    execute('int i = 3; while i > 0 { print i; i = i - 1; } print "go";')
    assert capsys.readouterr().out == "3\n2\n1\ngo\n"


# ---------- Области видимости ----------

def test_block_shadowing():
    # x внутри блока — отдельная переменная, внешняя не меняется
    assert values(execute("int x = 1; if 1 { int x = 2; x = 5; }")) == {"x": 1}


def test_block_sees_outer():
    assert values(execute("int x = 1, y; if 1 { y = x + 1; }")) == {"x": 1, "y": 2}


# ---------- Выполнение: массивы ----------

@pytest.mark.parametrize("src, expected", [
    ("int a[3];",                 {"a": ("int[]", [0, 0, 0])}),
    ("int a[0];",                 {"a": ("int[]", [])}),
    ("string s[2];",              {"s": ("string[]", ["", ""])}),
    ("int b = [7, 5, 2];",        {"b": ("int[]", [7, 5, 2])}),
    ('string s = ["a", "b"];',    {"s": ("string[]", ["a", "b"])}),
    ("int b = [1 + 1, 2 * 3];",   {"b": ("int[]", [2, 6])}),
    ("int n = 2; int a[n * 2];",  {"n": ("int", 2), "a": ("int[]", [0, 0, 0, 0])}),
    ("int a[2], b = [1], c;",     {"a": ("int[]", [0, 0]), "b": ("int[]", [1]), "c": ("int", 0)}),
    ("int b = [1, 2]; int c = b;", {"b": ("int[]", [1, 2]), "c": ("int[]", [1, 2])}),
])
def test_array_decl(src, expected):
    assert execute(src) == expected


def test_user_example():
    src = '''
        int a[100];
        int b = [7, 5, 2];
        resize(a, 50);
        int l = len(a);
    '''
    assert values(execute(src)) == {"a": [0] * 50, "b": [7, 5, 2], "l": 50}


@pytest.mark.parametrize("src, expected", [
    ("int a[3]; a[0] = 5;",                         {"a": [5, 0, 0]}),
    ("int a[3]; a[2] = 5; a[2] = a[2] + 1;",        {"a": [0, 0, 6]}),
    ("int a = [1, 2, 3]; int i = 1; a[i] = a[i - 1] + a[i + 1];",
                                                    {"a": [1, 4, 3], "i": 1}),
    ("int a = [1, 2, 3]; int x = a[a[0]];",         {"a": [1, 2, 3], "x": 2}),   # индекс — тоже выражение
    ('string s = ["a", "b"]; s[1] = s[1] + "!";',   {"s": ["a", "b!"]}),
    ("int a = [1, 2]; int b = [3]; a = b;",         {"a": [3], "b": [3]}),
    ("int a = [1, 2, 3]; resize(a, 5);",            {"a": [1, 2, 3, 0, 0]}),
    ("int a = [1, 2, 3]; resize(a, 1);",            {"a": [1]}),
    ("int a = [1, 2, 3]; resize(a, 0);",            {"a": []}),
    ("int a = [1, 2, 3]; resize(a, 3);",            {"a": [1, 2, 3]}),
    ('string s = ["a"]; resize(s, 2);',             {"s": ["a", ""]}),
    ("int a[1]; int n = 4; resize(a, n * 2);",      {"a": [0] * 8, "n": 4}),
    ("int a[3]; int l = len(a);",                   {"a": [0, 0, 0], "l": 3}),
    ("int a[0]; int l = len(a);",                   {"a": [], "l": 0}),
    ("int l = len([7, 5, 2]);",                     {"l": 3}),
    ("int a[2]; resize(a, 7); int l = len(a);",     {"a": [0] * 7, "l": 7}),
    ("int a = [1, 2]; int x = a[len(a) - 1];",      {"a": [1, 2], "x": 2}),     # последний элемент
    ("int a = [1, 2]; int x = len(a) * 10 + 1;",    {"a": [1, 2], "x": 21}),
])
def test_array_ops(src, expected):
    assert values(execute(src)) == expected


def test_array_is_reference():
    # второе имя для того же массива: изменения видны через оба
    src = "int a = [1, 2]; int c = a; c[0] = 9; resize(c, 3);"
    assert values(execute(src)) == {"a": [9, 2, 0], "c": [9, 2, 0]}


def test_array_in_block():
    src = "int a = [1, 2]; if 1 { a[0] = 5; int b = [3]; resize(a, len(b)); }"
    assert values(execute(src)) == {"a": [5]}


# ---------- Ошибки ----------
# все ошибки ловит компилятор, до выполнения

@pytest.mark.parametrize("src", [
    "int;",                                  # нет имени
    "int x = ;",                             # нет значения после =
    "int x = 1",                             # нет ;
    "int x 1;",                              # мусор между именем и ;
    "= 1;",                                  # нет типа
    "int x, ;",                              # запятая без имени
    "int x = 1, ;",                          # запятая без имени
    "int x = 1 2;",                          # лишний токен
    "int if = 1;",                           # ключевое слово вместо имени
    "int x; x = 1",                          # нет ; после присваивания
    "int x; x == 1;",                        # == вместо =
    "int x; if x > 0 x = 1;",                # нет {
    "int x; if x > 0 { x = 1;",              # нет }
    "int x; while x > 0 { x = x - 1;",       # нет }
    "int x; if x > 0 { } else x = 2;",       # после else нет { или if
    "else { }",                              # else без if
    "}",                                     # лишняя }
    "int a[];",                              # массив без размера
    "int a[3;",                              # нет ]
    "int a[3] = [1, 2, 3];",                 # размер и список сразу
    "int b = [];",                           # пустой список
    "int b = [1, 2;",                        # нет ]
    "int b = [1 2];",                        # нет запятой
    "int b = [1, ];",                        # запятая без элемента
    "int a[3]; a[0] 1;",                     # нет =
    "int a[3]; a[0];",                       # индекс без присваивания
    "int a[3]; resize(a);",                  # нет размера
    "int a[3]; resize(a, 5)",                # нет ;
    "int a[3]; resize a, 5;",                # нет скобок
    "int a[3]; print resize(a, 5);",         # resize — не выражение
    "int a[3]; len(a);",                     # len — не оператор
    "int a[3]; int l = len a;",              # нет скобок
    "int a[3]; int l = len(a;",              # нет )
    "int resize = 1;",                       # ключевые слова
    "int len = 1;",
    "[1, 2];",                               # список — не оператор
])
def test_syntax_errors(src):
    with pytest.raises(SyntaxError):
        compile_src(src)


@pytest.mark.parametrize("src", [
    "int x = 1; int x = 2;",                 # повторное объявление
    'int x = 1; string x = "a";',            # повторное с другим типом
    "int x=1, x=2;",                         # дубликат в одном объявлении
    "int x = abc;",                          # неизвестная переменная
    "y = 1;",                                # присваивание необъявленной
    "if 1 { int y = 1; } y = 2;",            # y видна только внутри блока
    "a[0] = 1;",                             # необъявленный массив
    "resize(a, 5);",
    "int l = len(a);",
    "int b = [x];",
])
def test_name_errors(src):
    with pytest.raises(NameError):
        compile_src(src)


@pytest.mark.parametrize("src", [
    'int x = "abc";',                        # строка в int
    "string s = 1;",                         # число в string
    "bool b = 1;",                           # неизвестный тип с инициализатором
    "bool b;",                               # неизвестный тип без инициализатора
    'int x; x = "a";',                       # присваивание строки в int
    'int x = 1 + "a";',                      # int + string
    'string s = "a" - "b";',                 # строки только складываются
    'string s = "a" * 2;',
    'int x = -"a";',
    'int x = 1 < "a";',                      # сравнение разных типов
    'if "a" { }',                            # условие не int
    "string s; while s { }",
    'int b = ["a"];',                        # строки в int-массив
    "string s = [1];",
    'int b = [1, "a"];',                     # элементы разных типов
    "int b = [[1]];",                        # вложенный массив
    "int x = 1; x[0] = 1;",                  # x — не массив
    "int x = 1; print x[0];",
    "int a[3]; a = 1;",                      # массиву — число
    "int a[3]; int x; x = a;",               # числу — массив
    "string s[2]; int b = s;",               # string[] в int
    'int a[3]; a[0] = "s";',                 # строка в элемент int
    'int a["x"];',                           # размер не int
    'int a[3]; a["x"] = 1;',                 # индекс не int
    'int a[3]; print a["x"];',
    'int a[3]; resize(a, "x");',
    "int x; resize(x, 5);",                  # resize и len не от массива
    "int x; print len(x);",
    'print len("abc");',
    "int a[3]; string l = len(a);",          # len даёт int
    "int a[3]; print a + a;",                # арифметика и сравнения с массивами
    "int a[3]; print a - a;",
    "int a[3]; print a * 2;",
    "int a[3]; print a == a;",
    "int a[3]; print -a;",
    "int a[3]; if a { }",
    "int a[3]; int x = a + 1;",
])
def test_type_errors(src):
    with pytest.raises(TypeError):
        compile_src(src)


@pytest.mark.parametrize("src, error", [
    ("int a[3]; print a[3];",      IndexError),   # выход за границы
    ("int a[3]; a[3] = 1;",        IndexError),
    ("int a[3]; print a[-1];",     IndexError),
    ("int a[0]; print a[0];",      IndexError),
    ("int a[-1];",                 ValueError),   # отрицательный размер
    ("int a[3]; resize(a, -1);",   ValueError),
])
def test_runtime_errors(src, error):
    # индекс и размер — выражения, компилятор их проверить не может
    compile_src(src)                             # компилируется без ошибок
    with pytest.raises(error):
        execute(src)
