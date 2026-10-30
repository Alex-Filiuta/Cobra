"""Сквозные тесты: на входе исходник на Cobra, на выходе — то, что напечатал print.
Запуск: pytest TestE2E.py -v"""

import io
from contextlib import redirect_stdout

import pytest
from Parser import execute


def output(src: str) -> str:
    """Компилирует и выполняет программу, возвращает всё, что она напечатала."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        execute(src)
    return buf.getvalue()


# ---------- Выражения ----------

@pytest.mark.parametrize("src, expected", [
    ("print 42;",             "42\n"),
    ("print 2 + 3 * 4;",      "14\n"),        # приоритет: умножение раньше
    ("print (2 + 3) * 4;",    "20\n"),
    ("print 10 - 2 - 3;",     "5\n"),         # слева направо, а не 10 - (2 - 3)
    ("print 100 / 10 / 2;",   "5\n"),
    ("print 7 / 2;",          "3\n"),         # целочисленное деление
    ("print -2 * 3;",         "-6\n"),
    ("print -(2 + 3);",       "-5\n"),
    ("print --5;",            "5\n"),
    ("print 1 < 2;",          "1\n"),         # сравнение даёт 1 или 0
    ("print 2 == 3;",         "0\n"),
    ("print (1 + 1) == 2;",   "1\n"),
    ("print 1000000 * 1000000;", "1000000000000\n"),   # переполнения нет
    ('print "hello";',        "hello\n"),
    ('print "a" + "b" + "c";', "abc\n"),
    ('print "";',             "\n"),
])
def test_expressions(src, expected):
    assert output(src) == expected


# ---------- Переменные ----------

@pytest.mark.parametrize("src, expected", [
    ("int x = 5; print x;",                      "5\n"),
    ("int x = 5; print x * x;",                  "25\n"),
    ("int x = 2, y = 3; print x + y; print x * y;", "5\n6\n"),
    ("int x; print x;",                          "0\n"),      # значение по умолчанию
    ("string s; print s;",                       "\n"),
    ('string s = "hi"; print s + "!";',          "hi!\n"),
    ("int x = 1; x = x + 1; x = x * 10; print x;", "20\n"),
    ("int x = 1; print x; x = 2; print x;",      "1\n2\n"),
    ("int x = 3; print -x; print x - 10;",       "-3\n-7\n"),
])
def test_variables(src, expected):
    assert output(src) == expected


# ---------- if / else if / else ----------

IF_CHAIN = "if x > 0 { x = 3 + x;} else if x == 0 {x =1;} else {x = 2;} print x;"


@pytest.mark.parametrize("start, expected", [(5, "8\n"), (0, "1\n"), (-3, "2\n")])
def test_if_chain(start, expected):
    assert output(f"int x = {start}; {IF_CHAIN}") == expected


@pytest.mark.parametrize("src, expected", [
    ('int x = 5; if x > 3 { print "big"; } print "done";',   "big\ndone\n"),
    ('int x = 1; if x > 3 { print "big"; } print "done";',   "done\n"),
    ('int x = 1; if x > 3 { print "big"; } else { print "small"; }', "small\n"),
    ('if 1 { print "yes"; }',                                "yes\n"),      # любое ненулевое — истина
    ('if 0 { print "yes"; } else { print "no"; }',           "no\n"),
])
def test_if(src, expected):
    assert output(src) == expected


SIGN = '''
    if x > 0 { print 1; }
    else if x < 0 { print -1; }
    else { print 0; }
'''


@pytest.mark.parametrize("x, expected", [(5, "1\n"), (-7, "-1\n"), (0, "0\n")])
def test_sign(x, expected):
    assert output(f"int x = {x};" + SIGN) == expected


def test_max_of_two():
    src = '''
        int a = 3, b = 8, m;
        if a > b { m = a; } else { m = b; }
        print m;
    '''
    assert output(src) == "8\n"


def test_abs():
    src = "int x = -5; if x < 0 { x = -x; } print x;"
    assert output(src) == "5\n"


def test_nested_if():
    src = '''
        int a = 1, b = 0;
        if a > 0 {
            if b > 0 { print "both"; } else { print "only a"; }
        } else {
            print "neither";
        }
    '''
    assert output(src) == "only a\n"


# ---------- while ----------

@pytest.mark.parametrize("src, expected", [
    ("int x = 0; while x>0 { x = x +1;} print x;",            "0\n"),   # тело не выполняется
    ("int i = 3; while i > 0 { print i; i = i - 1; }",         "3\n2\n1\n"),
    ("int i = 1; while i <= 5 { print i * i; i = i + 1; }",    "1\n4\n9\n16\n25\n"),
    ("int i = 10; while i > 0 { i = i - 3; } print i;",        "-2\n"),
])
def test_while(src, expected):
    assert output(src) == expected


def test_even_numbers():
    # if внутри while; остаток от деления через n - n / 2 * 2
    src = '''
        int i = 0;
        while i < 10 {
            if i == i / 2 * 2 { print i; }
            i = i + 1;
        }
    '''
    assert output(src) == "0\n2\n4\n6\n8\n"


def test_multiplication_table():
    src = '''
        int i = 1;
        while i <= 3 {
            int j = 1;
            while j <= 3 {
                print i * j;
                j = j + 1;
            }
            i = i + 1;
        }
    '''
    assert output(src) == "1\n2\n3\n2\n4\n6\n3\n6\n9\n"


def test_string_in_loop():
    src = '''
        int i = 0; string s = "";
        while i < 3 { s = s + "ab"; i = i + 1; }
        print s;
    '''
    assert output(src) == "ababab\n"


# ---------- Алгоритмы ----------

def test_factorial():
    src = '''
        int n = 5, f = 1;
        while n > 1 { f = f * n; n = n - 1; }
        print f;
    '''
    assert output(src) == "120\n"


def test_fibonacci():
    src = '''
        int a = 0, b = 1, i = 0;
        while i < 10 {
            print a;
            int t = a + b;
            a = b;
            b = t;
            i = i + 1;
        }
    '''
    assert output(src) == "0\n1\n1\n2\n3\n5\n8\n13\n21\n34\n"


def test_gcd():
    # алгоритм Евклида; остаток — через a - a / b * b
    src = '''
        int a = 48, b = 18;
        while b != 0 {
            int r = a - a / b * b;
            a = b;
            b = r;
        }
        print a;
    '''
    assert output(src) == "6\n"


def test_power():
    src = '''
        int base = 2, e = 10, r = 1;
        while e > 0 { r = r * base; e = e - 1; }
        print r;
    '''
    assert output(src) == "1024\n"


def test_sum_of_digits():
    src = '''
        int n = 1234, s = 0;
        while n > 0 {
            s = s + (n - n / 10 * 10);
            n = n / 10;
        }
        print s;
    '''
    assert output(src) == "10\n"


def test_reverse_number():
    src = '''
        int n = 1234, r = 0;
        while n > 0 {
            r = r * 10 + (n - n / 10 * 10);
            n = n / 10;
        }
        print r;
    '''
    assert output(src) == "4321\n"


IS_PRIME = '''
    int d = 2, prime = 1;
    while d * d <= n {
        if n - n / d * d == 0 { prime = 0; }
        d = d + 1;
    }
    print prime;
'''


@pytest.mark.parametrize("n, expected", [(2, "1\n"), (25, "0\n"), (91, "0\n"), (97, "1\n")])
def test_is_prime(n, expected):
    assert output(f"int n = {n};" + IS_PRIME) == expected


def test_collatz():
    # 6 -> 3 -> 10 -> 5 -> 16 -> 8 -> 4 -> 2 -> 1: восемь шагов
    src = '''
        int n = 6, steps = 0;
        while n != 1 {
            if n == n / 2 * 2 { n = n / 2; } else { n = 3 * n + 1; }
            steps = steps + 1;
        }
        print steps;
    '''
    assert output(src) == "8\n"


def test_fizzbuzz():
    # «и» для двух условий — сумма двух сравнений равна 2
    src = '''
        int i = 1;
        while i <= 15 {
            int by3 = i - i / 3 * 3 == 0;
            int by5 = i - i / 5 * 5 == 0;
            if by3 + by5 == 2 { print "FizzBuzz"; }
            else if by3 == 1 { print "Fizz"; }
            else if by5 == 1 { print "Buzz"; }
            else { print i; }
            i = i + 1;
        }
    '''
    expected = ["1", "2", "Fizz", "4", "Buzz", "Fizz", "7", "8", "Fizz", "Buzz",
                "11", "Fizz", "13", "14", "FizzBuzz"]
    assert output(src) == "".join(line + "\n" for line in expected)


# ---------- Массивы ----------

@pytest.mark.parametrize("src, expected", [
    ("int b = [7, 5, 2]; print b;",                     "[7, 5, 2]\n"),
    ("int a[3]; print a;",                              "[0, 0, 0]\n"),
    ('string s = ["a", "b"]; print s;',                 "['a', 'b']\n"),
    ("int b = [7, 5, 2]; print b[0]; print b[2];",      "7\n2\n"),
    ("int b = [7, 5, 2]; print b[0] + b[1] * b[2];",    "17\n"),
    ("int a[2]; a[0] = 1; a[1] = a[0] + 1; print a;",   "[1, 2]\n"),
    ("int b = [7, 5, 2]; print len(b);",                "3\n"),
    ("int a[100]; resize(a, 50); print len(a);",        "50\n"),
    ("int a = [1, 2, 3]; resize(a, 5); print a; resize(a, 2); print a;",
                                                        "[1, 2, 3, 0, 0]\n[1, 2]\n"),
    ("int a = [1, 2]; int c = a; c[0] = 9; print a;",   "[9, 2]\n"),   # массив — ссылка
    ("int a = [4, 8]; print a[len(a) - 1];",            "8\n"),        # последний элемент
])
def test_arrays(src, expected):
    assert output(src) == expected


def test_user_example():
    src = '''
        int a[100];
        int b = [7, 5, 2];
        resize(a, 50);
        int l = len(a);
        print l; print len(b); print a[49]; print b[1];
    '''
    assert output(src) == "50\n3\n0\n5\n"


def test_fill_squares():
    src = '''
        int n = 5; int a[n];
        int i = 0;
        while i < len(a) { a[i] = i * i; i = i + 1; }
        print a;
    '''
    assert output(src) == "[0, 1, 4, 9, 16]\n"


def test_array_sum():
    src = '''
        int a = [3, 1, 4, 1, 5, 9];
        int i = 0, s = 0;
        while i < len(a) { s = s + a[i]; i = i + 1; }
        print s;
    '''
    assert output(src) == "23\n"


def test_array_max():
    src = '''
        int a = [3, 1, 4, 1, 5, 9, 2, 6];
        int i = 1, m = a[0];
        while i < len(a) {
            if a[i] > m { m = a[i]; }
            i = i + 1;
        }
        print m;
    '''
    assert output(src) == "9\n"


def test_linear_search():
    src = '''
        int a = [10, 20, 30, 40];
        int i = 0, found = -1;
        while i < len(a) {
            if a[i] == 30 { found = i; }
            i = i + 1;
        }
        print found;
    '''
    assert output(src) == "2\n"


def test_reverse_in_place():
    src = '''
        int a = [1, 2, 3, 4, 5];
        int n = len(a), i = 0;
        while i < n / 2 {
            int t = a[i];
            a[i] = a[n - 1 - i];
            a[n - 1 - i] = t;
            i = i + 1;
        }
        print a;
    '''
    assert output(src) == "[5, 4, 3, 2, 1]\n"


def test_bubble_sort():
    src = '''
        int a = [5, 2, 9, 1, 7];
        int i = 0;
        while i < len(a) {
            int j = 0;
            while j < len(a) - 1 - i {
                if a[j] > a[j + 1] {
                    int t = a[j];
                    a[j] = a[j + 1];
                    a[j + 1] = t;
                }
                j = j + 1;
            }
            i = i + 1;
        }
        print a;
    '''
    assert output(src) == "[1, 2, 5, 7, 9]\n"


def test_grow_with_resize():
    # массив растёт по мере заполнения — добавление в конец через resize и len
    src = '''
        int a[0];
        int i = 1;
        while i <= 4 {
            resize(a, len(a) + 1);
            a[len(a) - 1] = i * 10;
            i = i + 1;
        }
        print a;
    '''
    assert output(src) == "[10, 20, 30, 40]\n"


def test_join_strings():
    src = '''
        string w = ["a", "b", "c"], s = "";
        int i = 0;
        while i < len(w) { s = s + w[i]; i = i + 1; }
        print s;
    '''
    assert output(src) == "abc\n"


def test_index_error_keeps_earlier_output():
    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(IndexError):
        execute("int a[2]; print a[1]; print a[2]; print 3;")
    assert buf.getvalue() == "0\n"


# ---------- Области видимости ----------

def test_block_shadowing():
    src = '''
        int x = 1;
        if 1 {
            int x = 2;
            print x;
        }
        print x;
    '''
    assert output(src) == "2\n1\n"


def test_block_sees_outer():
    src = '''
        int x = 10;
        while x > 0 {
            int y = x * 2;
            print y;
            x = x - 5;
        }
    '''
    assert output(src) == "20\n10\n"


def test_loop_variable_reset_each_iteration():
    # t объявляется заново на каждом проходе и снова равна 0
    src = '''
        int i = 0;
        while i < 3 {
            int t;
            t = t + i;
            print t;
            i = i + 1;
        }
    '''
    assert output(src) == "0\n1\n2\n"


# ---------- Программы без вывода ----------

@pytest.mark.parametrize("src", [
    "",
    "int x = 1; x = x + 1;",
    "int x = 0; if x > 0 { print x; }",
    "int x = 0; while x > 0 { print x; }",
])
def test_no_output(src):
    assert output(src) == ""


# ---------- Форматирование не влияет на результат ----------

@pytest.mark.parametrize("src", [
    "int x=1;if x>0{print x;}else{print 0;}",
    "int x = 1; if x > 0 { print x; } else { print 0; }",
    "int\tx\t=\t1;\nif\tx\t>\t0\t{\nprint\tx;\n}\nelse\t{\nprint\t0;\n}",
    '''
        int x = 1;
        if x > 0
        {
            print x;
        }
        else
        {
            print 0;
        }
    ''',
])
def test_formatting(src):
    assert output(src) == "1\n"


# ---------- Ошибки ----------

@pytest.mark.parametrize("src, error", [
    ('print 1; int x = "a";',        TypeError),
    ("print 1; print y;",            NameError),
    ("print 1; print 2",             SyntaxError),
    ("print 1; if 1 { print 2;",     SyntaxError),
])
def test_compile_error_prints_nothing(src, error):
    # ошибки находит компилятор, поэтому программа не успевает ничего напечатать
    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(error):
        execute(src)
    assert buf.getvalue() == ""


def test_runtime_error_keeps_earlier_output():
    # деление на переменную компилятор проверить не может — ошибка при выполнении,
    # и всё, что напечатано до неё, остаётся
    buf = io.StringIO()
    with redirect_stdout(buf), pytest.raises(ZeroDivisionError):
        execute("print 1; int z; print 10 / z; print 2;")
    assert buf.getvalue() == "1\n"
