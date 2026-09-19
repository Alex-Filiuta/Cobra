"""Тесты для мини-языка из lang.py. Запуск: pytest test_lang.py -v"""

import pytest
from Parser import Parser, DeclStmt, execute


def parse(src: str):
    return Parser(src).parse()


def values(result: dict) -> dict:
    """{name: (type, value)} -> {name: value}"""
    return {name: v for name, (_, v) in result.items()}


# ---------- Парсер: успешные разборы ----------

@pytest.mark.parametrize("src, expected", [
    ("int x = 1;",        [DeclStmt("int", "x", 1)]),
    ("int x;",            [DeclStmt("int", "x", None)]),
    ('string c = "abc";', [DeclStmt("string", "c", "abc")]),
    ('string s = "";',    [DeclStmt("string", "s", "")]),
    ("int x, y;",         [DeclStmt("int", "x", None),
                           DeclStmt("int", "y", None)]),
    ("int x=1, y=2;",     [DeclStmt("int", "x", 1),
                           DeclStmt("int", "y", 2)]),
    ("int x, y = 5, z;",  [DeclStmt("int", "x", None),
                           DeclStmt("int", "y", 5),
                           DeclStmt("int", "z", None)]),
])
def test_parse_ok(src, expected):
    assert parse(src) == expected


@pytest.mark.parametrize("src", [
    "int x=1;",
    "int  x  =  1 ;",
    "int\tx\t=\t1\t;",
    "  int x = 1;  ",
    "int\nx\n=\n1\n;",
])
def test_whitespace_tolerance(src):
    assert parse(src) == [DeclStmt("int", "x", 1)]


def test_multiple_statements():
    program = parse('int x = 1; int y; string s = "hi";')
    assert program == [
        DeclStmt("int", "x", 1),
        DeclStmt("int", "y", None),
        DeclStmt("string", "s", "hi"),
    ]


# ---------- Интерпретатор ----------

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


# ---------- Ошибки ----------

@pytest.mark.parametrize("src", [
    "int;",          # нет имени
    "int x = ;",     # нет значения после =
    "int x = 1",     # нет ;
    "int x 1;",      # мусор между именем и ;
    "int x = abc;",  # значение не число/строка
    "= 1;",          # нет типа
    "int x, ;",      # запятая без имени
    "int x = 1, ;",  # запятая без имени
    "int x = 1 2;",  # лишний токен
])
def test_syntax_errors(src):
    with pytest.raises(SyntaxError):
        Parser(src).parse()


@pytest.mark.parametrize("src", [
    "int x = 1; int x = 2;",        # повторное объявление
    'int x = 1; string x = "a";',   # повторное с другим типом
    "int x=1, x=2;",                # дубликат в одном объявлении
])
def test_name_errors(src):
    with pytest.raises(NameError):
        execute(src)


# @pytest.mark.parametrize("src", [
#     'int x = "abc";',   # строка в int
#     "string s = 1;",    # число в string
#     "bool b = 1;",      # неизвестный тип с инициализатором
#     "bool b;",          # неизвестный тип без инициализатора
# ])
# def test_type_errors(src):
#     with pytest.raises(TypeError):
#         execute(src)