"""Тесты стековой машины из VM.py: байт-код пишется вручную, без компилятора.
Запуск: pytest TestVM.py -v"""

import pytest
from VM import run


def result(code: list[tuple]):
    """Выполняет код, оставляющий на стеке одно значение, и возвращает его."""
    return run(code + [("STORE", 0)], 1)[0]


# ---------- Память: PUSH, STORE, LOAD ----------

def test_empty_program():
    assert run([], 0) == []


def test_memory_size():
    # незаписанные ячейки остаются None
    assert run([("PUSH", 1), ("STORE", 0)], 3) == [1, None, None]


@pytest.mark.parametrize("value", [0, 42, -7, "", "abc"])
def test_push_store(value):
    assert run([("PUSH", value), ("STORE", 0)], 1) == [value]


def test_load_copies_value():
    code = [("PUSH", 7), ("STORE", 0), ("LOAD", 0), ("STORE", 1)]
    assert run(code, 2) == [7, 7]


def test_store_overwrites():
    code = [("PUSH", 1), ("STORE", 0), ("PUSH", 2), ("STORE", 0)]
    assert run(code, 1) == [2]


def test_stack_is_lifo():
    # последнее положенное снимается первым
    code = [("PUSH", 1), ("PUSH", 2), ("STORE", 0), ("STORE", 1)]
    assert run(code, 2) == [2, 1]


# ---------- Арифметика и сравнения ----------

@pytest.mark.parametrize("op, a, b, expected", [
    ("ADD", 2, 3, 5),
    ("SUB", 7, 2, 5),
    ("SUB", 2, 7, -5),           # порядок: a - b, где a положили первым
    ("MUL", 4, 5, 20),
    ("DIV", 7, 2, 3),
    ("DIV", 2, 7, 0),
    ("DIV", -7, 2, -4),          # округление вниз, как // в Python
    ("ADD", "ab", "c", "abc"),   # склейка строк
])
def test_arithmetic(op, a, b, expected):
    assert result([("PUSH", a), ("PUSH", b), (op,)]) == expected


@pytest.mark.parametrize("op, a, b, expected", [
    ("EQ", 1, 1, 1), ("EQ", 1, 2, 0),
    ("NE", 1, 2, 1), ("NE", 1, 1, 0),
    ("LT", 1, 2, 1), ("LT", 2, 1, 0), ("LT", 1, 1, 0),
    ("GT", 2, 1, 1), ("GT", 1, 2, 0), ("GT", 1, 1, 0),
    ("LE", 1, 2, 1), ("LE", 1, 1, 1), ("LE", 2, 1, 0),
    ("GE", 2, 1, 1), ("GE", 1, 1, 1), ("GE", 1, 2, 0),
    ("EQ", "a", "a", 1), ("NE", "a", "b", 1), ("LT", "a", "b", 1),
])
def test_compare(op, a, b, expected):
    value = result([("PUSH", a), ("PUSH", b), (op,)])
    assert value == expected
    assert type(value) is int            # именно 1 или 0, а не True / False


@pytest.mark.parametrize("value, expected", [(5, -5), (-5, 5), (0, 0)])
def test_neg(value, expected):
    assert result([("PUSH", value), ("NEG",)]) == expected


def test_nested_expression():
    # (2 + 3) * -(10 - 4) = -30
    code = [
        ("PUSH", 2), ("PUSH", 3), ("ADD",),
        ("PUSH", 10), ("PUSH", 4), ("SUB",), ("NEG",),
        ("MUL",),
    ]
    assert result(code) == -30


# ---------- Переходы ----------

def test_jmp_skips_code():
    code = [
        ("PUSH", 1), ("STORE", 0),           # 0-1
        ("JMP", 5),                          # 2     прыжок за конец — программа завершается
        ("PUSH", 2), ("STORE", 0),           # 3-4   не выполняется
    ]
    assert run(code, 1) == [1]


@pytest.mark.parametrize("cond, expected", [
    (0, "перешли"),
    (1, "не перешли"),
    (-1, "не перешли"),                      # любое ненулевое значение — истина
])
def test_jz(cond, expected):
    code = [
        ("PUSH", cond), ("JZ", 5),           # 0-1
        ("PUSH", "не перешли"), ("STORE", 0),  # 2-3
        ("JMP", 7),                          # 4
        ("PUSH", "перешли"), ("STORE", 0),   # 5-6
    ]
    assert run(code, 1) == [expected]


@pytest.mark.parametrize("cond", [0, 1])
def test_jz_pops_condition(cond):
    # условие снимается со стека в обоих случаях, под ним остаётся 9
    code = [("PUSH", 9), ("PUSH", cond), ("JZ", 3), ("STORE", 0)]
    assert run(code, 1) == [9]


def test_loop_sum():
    # s = 0; i = 1; while i <= 5 { s = s + i; i = i + 1; }
    code = [
        ("PUSH", 0), ("STORE", 0),                           # 0-1    s = 0
        ("PUSH", 1), ("STORE", 1),                           # 2-3    i = 1
        ("LOAD", 1), ("PUSH", 5), ("LE",), ("JZ", 17),       # 4-7    i <= 5 ?
        ("LOAD", 0), ("LOAD", 1), ("ADD",), ("STORE", 0),    # 8-11   s = s + i
        ("LOAD", 1), ("PUSH", 1), ("ADD",), ("STORE", 1),    # 12-15  i = i + 1
        ("JMP", 4),                                          # 16
    ]
    assert run(code, 2) == [15, 6]


def test_long_loop():
    # 10000 проходов: машина работает циклом, без рекурсии, и не упирается в лимиты Python
    code = [
        ("PUSH", 10000), ("STORE", 0),                       # 0-1    i = 10000
        ("LOAD", 0), ("PUSH", 0), ("GT",), ("JZ", 11),       # 2-5    i > 0 ?
        ("LOAD", 0), ("PUSH", 1), ("SUB",), ("STORE", 0),    # 6-9    i = i - 1
        ("JMP", 2),                                          # 10
    ]
    assert run(code, 1) == [0]


# ---------- Массивы ----------

@pytest.mark.parametrize("code, expected", [
    ([("PUSH", 3), ("NEWARR", 0)],   [0, 0, 0]),
    ([("PUSH", 2), ("NEWARR", "")],  ["", ""]),
    ([("PUSH", 0), ("NEWARR", 0)],   []),
    ([("PUSH", 7), ("PUSH", 5), ("PUSH", 2), ("BUILD", 3)], [7, 5, 2]),   # порядок сохраняется
    ([("PUSH", "a"), ("BUILD", 1)],  ["a"]),
    ([("BUILD", 0)],                 []),
])
def test_make_array(code, expected):
    assert result(code) == expected


def test_build_pops_only_n():
    code = [("PUSH", 1), ("PUSH", 2), ("PUSH", 3), ("BUILD", 2), ("STORE", 0), ("STORE", 1)]
    assert run(code, 2) == [[2, 3], 1]


@pytest.mark.parametrize("index, expected", [(0, 7), (1, 5), (2, 2)])
def test_loadi(index, expected):
    code = [("PUSH", 7), ("PUSH", 5), ("PUSH", 2), ("BUILD", 3), ("PUSH", index), ("LOADI",)]
    assert result(code) == expected


def test_storei():
    code = [("PUSH", 3), ("NEWARR", 0), ("STORE", 0),
            ("LOAD", 0), ("PUSH", 1), ("PUSH", 9), ("STOREI",)]
    assert run(code, 1) == [[0, 9, 0]]


def test_storei_pops_all_three():
    # под массивом, индексом и значением лежит 42 — после STOREI оно на вершине
    code = [("PUSH", 3), ("NEWARR", 0), ("STORE", 0), ("PUSH", 42),
            ("LOAD", 0), ("PUSH", 1), ("PUSH", 9), ("STOREI",), ("STORE", 1)]
    assert run(code, 2) == [[0, 9, 0], 42]


def test_array_is_shared():
    # STORE копирует ссылку: обе ячейки указывают на один массив
    code = [("PUSH", 2), ("NEWARR", 0), ("STORE", 0), ("LOAD", 0), ("STORE", 1),
            ("LOAD", 1), ("PUSH", 0), ("PUSH", 5), ("STOREI",),
            ("LOAD", 0), ("PUSH", 0), ("LOADI",), ("STORE", 2)]
    assert run(code, 3) == [[5, 0], [5, 0], 5]


@pytest.mark.parametrize("n, expected", [
    (5, [1, 2, 3, 0, 0]),                    # удлинить
    (1, [1]),                                # укоротить
    (0, []),
    (3, [1, 2, 3]),                          # без изменений
])
def test_resize(n, expected):
    code = [("PUSH", 1), ("PUSH", 2), ("PUSH", 3), ("BUILD", 3), ("STORE", 0),
            ("LOAD", 0), ("PUSH", n), ("RESIZE", 0)]
    assert run(code, 1) == [expected]


def test_resize_in_place():
    # меняется сам массив, а не создаётся новый — видно через вторую ссылку
    code = [("PUSH", 1), ("NEWARR", 0), ("STORE", 0), ("LOAD", 0), ("STORE", 1),
            ("LOAD", 1), ("PUSH", 3), ("RESIZE", 7)]
    assert run(code, 2) == [[0, 7, 7], [0, 7, 7]]


def test_resize_string_default():
    code = [("PUSH", 1), ("NEWARR", ""), ("STORE", 0), ("LOAD", 0), ("PUSH", 2), ("RESIZE", "")]
    assert run(code, 1) == [["", ""]]


@pytest.mark.parametrize("code, expected", [
    ([("PUSH", 3), ("NEWARR", 0), ("LEN",)],                                   3),
    ([("BUILD", 0), ("LEN",)],                                                 0),
    ([("PUSH", 1), ("NEWARR", 0), ("STORE", 0),
      ("LOAD", 0), ("PUSH", 10), ("RESIZE", 0), ("LOAD", 0), ("LEN",)],       10),
])
def test_len(code, expected):
    assert result(code) == expected


def test_len_pops_array():
    code = [("PUSH", 42), ("PUSH", 2), ("NEWARR", 0), ("LEN",), ("STORE", 0), ("STORE", 1)]
    assert run(code, 2) == [2, 42]


@pytest.mark.parametrize("index", [3, -1, 100])
def test_index_out_of_range(index):
    code = [("PUSH", 3), ("NEWARR", 0), ("PUSH", index), ("LOADI",)]
    with pytest.raises(IndexError, match="по адресу 3"):
        run(code, 0)


def test_storei_out_of_range():
    code = [("PUSH", 3), ("NEWARR", 0), ("PUSH", 3), ("PUSH", 1), ("STOREI",)]
    with pytest.raises(IndexError):
        run(code, 0)


@pytest.mark.parametrize("code", [
    [("PUSH", -1), ("NEWARR", 0)],
    [("PUSH", 1), ("NEWARR", 0), ("PUSH", -1), ("RESIZE", 0)],
])
def test_negative_size(code):
    with pytest.raises(ValueError):
        run(code, 0)


# ---------- PRINT ----------

def test_print(capsys):
    run([("PUSH", 42), ("PRINT",), ("PUSH", "hi"), ("PRINT",)], 0)
    assert capsys.readouterr().out == "42\nhi\n"


def test_print_pops(capsys):
    code = [("PUSH", 1), ("PUSH", 2), ("PRINT",), ("STORE", 0)]
    assert run(code, 1) == [1]
    assert capsys.readouterr().out == "2\n"


# ---------- Ошибки ----------

@pytest.mark.parametrize("instr", [
    ("HALT",),                               # такой команды нет
    ("PUSH",),                               # нет аргумента
    ("JMP",),
    ("ADD", 1),                              # лишний аргумент
])
def test_bad_instruction(instr):
    with pytest.raises(RuntimeError, match="по адресу 1"):
        run([("PUSH", 0), instr], 0)


def test_division_by_zero():
    with pytest.raises(ZeroDivisionError):
        run([("PUSH", 1), ("PUSH", 0), ("DIV",)], 0)


def test_empty_stack():
    # на стеке одно значение, а ADD нужно два
    with pytest.raises(IndexError):
        run([("PUSH", 1), ("ADD",)], 0)
