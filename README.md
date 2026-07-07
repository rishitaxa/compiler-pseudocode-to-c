# Pseudocode to C Compiler

A simple compiler that translates structured pseudocode into valid C code.

This project demonstrates the fundamental phases of compiler construction—from lexical analysis and parsing to code generation—by converting human-readable pseudocode into compilable C programs.

---

## ✨ Features

* Convert structured pseudocode into C
* Supports common programming constructs:

  * Variable declarations
  * Input and output statements
  * Arithmetic expressions
  * Conditional statements (`IF`, `ELSE`)
  * Loops (`WHILE`, `FOR`, etc.)
* Generates clean and readable C code
* Easy to extend with additional language features

---

## 📂 Project Structure

```
compiler-pseudocode-to-c/
│
├── lexer/          # Lexical analysis
├── parser/         # Syntax analysis
├── generator/      # C code generation
├── examples/       # Sample pseudocode programs
├── output/         # Generated C programs
├── main.*          # Compiler entry point
└── README.md
```

> *The folder names may differ slightly depending on the project structure.*

---

## ⚙️ How It Works

The compiler follows the traditional compilation pipeline:

```
Pseudocode
      │
      ▼
Lexical Analysis
      │
      ▼
Syntax Parsing
      │
      ▼
Semantic Processing
      │
      ▼
C Code Generation
      │
      ▼
Generated C Program
```

---

## 🚀 Getting Started

### Clone the repository

```bash
git clone https://github.com/rishitaxa/compiler-pseudocode-to-c.git
cd compiler-pseudocode-to-c
```

### Build

Compile the project according to your implementation.

Example:

```bash
gcc *.c -o compiler
```

or if you're using Flex/Bison:

```bash
flex lexer.l
bison -d parser.y
gcc lex.yy.c parser.tab.c -o compiler
```

---

## ▶️ Usage

Run the compiler:

```bash
./compiler input.txt
```

Example pseudocode:

```text
BEGIN

READ a
READ b

sum = a + b

PRINT sum

END
```

Generated C:

```c
#include <stdio.h>

int main() {
    int a, b, sum;

    scanf("%d", &a);
    scanf("%d", &b);

    sum = a + b;

    printf("%d\n", sum);

    return 0;
}
```

Compile the generated C program:

```bash
gcc output.c -o output
./output
```

---

## 🧠 Compiler Phases

### 1. Lexical Analysis

Breaks the input pseudocode into tokens such as:

* Keywords
* Identifiers
* Numbers
* Operators
* Delimiters

### 2. Parsing

Checks whether the input follows the grammar of the pseudocode language and constructs a syntax tree.

### 3. Semantic Analysis

Performs validation such as variable usage and expression correctness.

### 4. Code Generation

Produces equivalent C source code that can be compiled using any standard C compiler.

---

## 📚 Example

### Input

```text
BEGIN

READ n

IF n > 0 THEN
    PRINT "Positive"
ELSE
    PRINT "Negative"
ENDIF

END
```

### Output

```c
#include <stdio.h>

int main() {
    int n;

    scanf("%d", &n);

    if (n > 0)
        printf("Positive\n");
    else
        printf("Negative\n");

    return 0;
}
```

---

## 🎯 Learning Objectives

This project is useful for understanding:

* Compiler Design
* Lexical Analysis
* Parsing
* Context-Free Grammars
* Syntax Trees
* Code Generation
* Programming Language Translation

---

## 🛠 Technologies Used

* C
* Flex (Lex) *(if applicable)*
* Bison (Yacc) *(if applicable)*
* GCC

---

## 🤝 Contributing

Contributions are welcome!

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Open a Pull Request

---

## 📄 License

This project is open source and available under the MIT License (or your preferred license).

---

## 👨‍💻 Author

**Rishita Sharma**

GitHub: https://github.com/rishitaxa

---

⭐ If you found this project helpful, consider giving it a star!
