"""Стековая машина: выполняет байт-код, который генерирует Parser.py.

Команда — кортеж из имени и, если нужно, аргумента: ("PUSH", 1), ("ADD",).

    PUSH v    положить константу v на стек
    LOAD n    положить значение из ячейки n
    STORE n   снять вершину стека в ячейку n
    ADD SUB MUL DIV       снять два значения, положить результат
    EQ NE LT GT LE GE     снять два значения, положить 1 или 0
    NEG       сменить знак вершины
    JMP a     перейти на адрес a
    JZ a      снять вершину; если она 0 — перейти на адрес a
    PRINT     снять вершину и напечатать

    NEWARR d  снять размер n, положить массив из n значений d
    BUILD n   снять n значений, положить массив из них (в том же порядке)
    LOADI     снять индекс и массив, положить элемент массива
    STOREI    снять значение, индекс и массив, записать значение в элемент
    RESIZE d  снять размер n и массив, изменить размер массива на месте:
              лишние элементы отбрасываются, новые получают значение d
    LEN       снять массив, положить его текущий размер

Массив — обычный список Python, в ячейке памяти лежит ссылка на него.
"""

import operator


BINARY = {
    "ADD": operator.add,
    "SUB": operator.sub,
    "MUL": operator.mul,
    "DIV": operator.floordiv,
    "EQ":  lambda a, b: int(a == b),
    "NE":  lambda a, b: int(a != b),
    "LT":  lambda a, b: int(a < b),
    "GT":  lambda a, b: int(a > b),
    "LE":  lambda a, b: int(a <= b),
    "GE":  lambda a, b: int(a >= b),
}


def check_index(arr: list, index: int, addr: int) -> int:
    if not 0 <= index < len(arr):
        raise IndexError(f"Индекс {index} вне массива длины {len(arr)} по адресу {addr}")
    return index


def check_size(n: int, addr: int) -> int:
    if n < 0:
        raise ValueError(f"Отрицательный размер массива {n} по адресу {addr}")
    return n


def run(code: list[tuple], n_vars: int) -> list:
    """Выполняет байт-код, возвращает память (список значений ячеек)."""
    stack, memory, pc = [], [None] * n_vars, 0
    while pc < len(code):
        instr = code[pc]
        pc += 1
        match instr:
            case ("PUSH", value):
                stack.append(value)
            case ("LOAD", slot):
                stack.append(memory[slot])
            case ("STORE", slot):
                memory[slot] = stack.pop()
            case ("NEG",):
                stack.append(-stack.pop())
            case ("JMP", target):
                pc = target
            case ("JZ", target):
                if stack.pop() == 0:
                    pc = target
            case ("PRINT",):
                print(stack.pop())
            case (op,) if op in BINARY:
                right = stack.pop()
                stack.append(BINARY[op](stack.pop(), right))
            case ("NEWARR", default):
                stack.append([default] * check_size(stack.pop(), pc - 1))
            case ("BUILD", n):
                items = [stack.pop() for _ in range(n)]
                stack.append(items[::-1])
            case ("LOADI",):
                index, arr = stack.pop(), stack.pop()
                stack.append(arr[check_index(arr, index, pc - 1)])
            case ("STOREI",):
                value, index, arr = stack.pop(), stack.pop(), stack.pop()
                arr[check_index(arr, index, pc - 1)] = value
            case ("RESIZE", default):
                n, arr = check_size(stack.pop(), pc - 1), stack.pop()
                del arr[n:]                                  # укоротить
                arr.extend([default] * (n - len(arr)))       # или удлинить
            case ("LEN",):
                stack.append(len(stack.pop()))
            case _:
                raise RuntimeError(f"Неизвестная команда {instr} по адресу {pc - 1}")
    return memory


def dump(code: list[tuple]):
    """Печатает байт-код с адресами."""
    for addr, (op, *args) in enumerate(code):
        print(f"{addr:4}  {op:<6}", *map(repr, args))


if __name__ == "__main__":
    # машина не зависит от компилятора — байт-код можно написать руками:
    # int i = 3; while i > 0 { print i; i = i - 1; }
    code = [
        ("PUSH", 3), ("STORE", 0),                               # 0-1
        ("LOAD", 0), ("PUSH", 0), ("GT",), ("JZ", 13),           # 2-5
        ("LOAD", 0), ("PRINT",),                                 # 6-7
        ("LOAD", 0), ("PUSH", 1), ("SUB",), ("STORE", 0),        # 8-11
        ("JMP", 2),                                              # 12
    ]
    dump(code)
    run(code, n_vars=1)
