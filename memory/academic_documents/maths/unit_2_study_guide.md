# Unit 2: Linear Algebra in Mathematics

## Chapter 1: Vector Spaces

### Definition of a Vector Space
A vector space is a mathematical structure that consists of a set of elements (called vectors) and a binary operation (called addition), which combines two vectors to produce another vector. The set of all vectors forms a vector space under this operation.

#### Subtopics:
- **Vector Spaces**: A collection of vectors where the operations are defined.
- **Subspaces**: Subsets of a vector space that satisfy certain conditions.
- **Spanning Sets**: Vectors in the vector space that can be used to form any vector in the space.
- **Linear Independence**: A set of vectors is linearly independent if they cannot be expressed as a linear combination of other vectors.

### Example: Real Numbers
The real numbers \(\mathbb{R}\) are a vector space over the field \(\mathbb{Q}\), where \(\mathbb{Q}\) represents the rational numbers. The operations in this vector space include addition, subtraction, and multiplication by scalars (real numbers).

#### Code Example:
```python
import numpy as np

# Define real numbers
R = np.arange(10)

# Additive identity
identity = R + 0

# Scalar multiplication
scalar = 2
result = scalar * R

print("Real Numbers:", R)
print("Additive Identity:", identity)
print("Scalar Multiplication:", result)
```

### Formulas and Notations
- **Vector Space**: \( V \) (vector space over \(\mathbb{R}\))
- **Subspace**: \( S \subseteq V \) such that every vector in \( S \) can be expressed as a linear combination of vectors in \( S \).
- **Spanning Set**: A set of vectors that are linearly independent and span the entire vector space.

### Example: Vector Space over \(\mathbb{Q}\)
Consider the vector space \(\mathbb{R}^2\) (the plane) with addition defined as:
\[ (x_1, x_2) + (y_1, y_2) = (x_1 + y_1, x_2 + y_2). \]

#### Code Example:
```python
import numpy as np

# Define vectors in R^2
v1 = np.array([1, 2])
v2 = np.array([3, 4])

# Addition
result = v1 + v2

print("Vector Addition:", result)
```

### Linear Independence
A set of vectors is linearly independent if the only solution to the equation \( c_1 \mathbf{u} + c_2 \mathbf{v} = \mathbf{0} \) is \( c_1 = 0, c_2 = 0 \).

#### Example:
Consider the set of vectors \(\{(1, 0), (0, 1)\}\). These vectors are linearly independent because there is no non-trivial solution to the equation:

\[ c_1 (1, 0) + c_2 (0, 1) = (0, 0). \]

#### Code Example:
```python
import numpy as np

# Define vectors in R^2
v1 = np.array([1, 0])
v2 = np.array([0, 1])

# Check linear independence
is_linearly_independent = v1[0] * v2[0] + v1[1] * v2[1] == 0

print("Vectors are Linearly Independent:", is_linearly_independent)
```

### Matrix Representation and Invertibility
A matrix \( A \) in a vector space can be represented as an infinite-dimensional array of scalars. The determinant of \( A \), denoted \( \det(A) \), gives the volume scaling factor when multiplying \( A \) by a unit vector.

#### Example:
Consider the 2x2 matrix:

\[ A = \begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}. \]

The determinant of this matrix is:

\[ \det(A) = (1)(1) - (0)(0) = 1. \]

#### Code Example:
```python
import numpy as np

# Define a 2x2 matrix
A = np.array([[1, 0], [0, 1]])

# Calculate the determinant
determinant = np.linalg.det(A)

print("Determinant of A:", determinant)
```

### Inverse Matrix
The inverse of a matrix \( A \) is defined as:

\[ A^{-1} = \frac{1}{\det(A)} \text{adj}(A), \]

where \(\text{adj}(A)\) is the adjugate matrix, which is the transpose of the cofactor matrix.

#### Example:
Consider