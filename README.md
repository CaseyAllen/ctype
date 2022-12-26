# Cype CLI

### A CLI for grabbing the actual definitions of those pesky C types


## Usage

  ```bash
  ctype TYPENAME header_files
  ```

  **Optional Flags**:
  - `-p`:
    `p`rint a full, human-friendly type


## Output Reference

- **Primitives**:
    All primitive types follow the general layout `P<s>` where `P` is the primitive prefix and `<s>` is a set of 4 bytes (big-endian) representing the primitive size in bits (with the exception of void and bool)   
    **prefixes**:
    - `i`: A signed integer
    - `u`: An unsigned integer
    - `f`: A floating-point number
    - `v`: void
    - `b`: a boolean value

---

- **Pointers**:
  A pointer is expressed as `pT` where `T` is any type

---

- **Structs**:
  Structs are a little more complex and are represented using the following rules:
  - byte 1: `S` prefix
  - byte 2-5: number of members (big-endian)
  - for each member (separated by the `|` character):
    - name (as a null-terminated c-string)
    - type
 
---

- **Unions**:
  The representation of unions is almost identical to structs except the first byte is the `U` character



