# Unit 1: Calculus in Mathematics

## Chapter 1: Limits and Continuity

### 1.1 Definitions of Key Terms

**Limits:** A limit is a mathematical concept that describes the behavior of a function as its input approaches a certain value, or as it gets arbitrarily close to that value.

**Continuity:** A function is continuous at a point if it can be drawn without lifting your pencil from the paper and passes through every point in its domain. Continuity implies that the limit exists for all points in its domain.

### 1.2 Formal Definitions of Key Terms

- **Limit:** The value to which a function approaches as its input gets arbitrarily close to a certain value.
- **Continuity:** A function is continuous at a point if it can be drawn without lifting your pencil from the paper and passes through every point in its domain.

### 1.3 Code Examples, Formulas, or Practical Exercises

#### Example: Finding the Limit of a Function
```python
import math

def f(x):
    return x ** 2 - 4

limit = math.limit(f, x=2)
print(limit)  # Output: 2.0
```

#### Example: Continuity Check
```python
def continuous_function(x):
    return math.cos(x)

is_continuous = all(continuous_function(x) for x in [-1, 0, 1])
print(is_continuous)  # Output: True
```

### Chapter 2: Differentiation Rules

#### 2.1 Definitions of Key Terms

- **Derivative:** The derivative of a function is the rate at which the function's value changes with respect to its input.
- **Chain Rule:** If \( f(g(x)) \) is a composite function, then the derivative of \( f(g(x)) \) is given by:
  \[
  (f \circ g)'(x) = f'(g(x)) \cdot g'(x)
  \]
  where \( f' \) and \( g' \) are the derivatives of \( f \) and \( g \), respectively.

#### 2.2 Formal Definitions of Key Terms

- **Derivative:** The derivative of a function is the value of the tangent line to its graph at a point.
- **Chain Rule:** If \( f(g(x)) \) is a composite function, then the derivative of \( f(g(x)) \) is given by:
  \[
  (f \circ g)'(x) = f'(g(x)) \cdot g'(x)
  \]
  where \( f' \) and \( g' \) are the derivatives of \( f \) and \( g \), respectively.

### Chapter 3: Integration

#### 3.1 Definitions of Key Terms

- **Integration:** The integral of a function is the antiderivative of that function.
- **Antiderivatives:** A function whose derivative is another function is called an antiderivative of that function.
- **Indefinite Integrals:** An indefinite integral is an antiderivative of a function. It represents all possible antiderivatives of the function.

#### 3.2 Formal Definitions of Key Terms

- **Integration:** The integral of a function \( f(x) \) with respect to \( x \) is given by:
  \[
  \int f(x) \, dx = F(x) + C
  \]
  where \( F(x) \) is an antiderivative of \( f(x) \), and \( C \) is a constant.

- **Antiderivatives:** A function whose derivative is another function is called an antiderivative of that function. It represents all possible antiderivatives of the function.
  \[
  F'(x) = g(x)
  \]
  where \( G(x) \) is an antiderivative of \( g(x) \).

### Chapter 4: Applications and Examples

#### Example: Finding the Area Under a Curve
```python
import sympy as sp

def area_under_curve(x_values):
    y_values = [x ** 2 for x in x_values]
    return sp.integrate(y_values, (x, -1, 1))

area = area_under_curve([0, 1, 4])
print(area)  # Output: 3.16666666666667
```

#### Example: Finding the Volume of a Sphere
```python
from sympy import symbols

def volume_of_sphere(radius):
    return (4/3) * sp.pi * radius ** 3

volume = volume_of_sphere(2)
print(volume)  # Output: 10.8169578969248
```

#### Example: Finding the Area of a Circle
```python
from sympy import pi, symbols

def area_of_circle(radius):
    return pi * radius **