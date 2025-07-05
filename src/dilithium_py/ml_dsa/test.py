# Goal : Matrix * Matrix
from dilithium_py.polynomials.polynomials_generic import PolynomialRing
from dilithium_py.modules.modules_generic import Module
import random

q = 8380417
n = 256
k = 4

def BinaryToRing(binary):
    R = PolynomialRing(q, n)
    coeffs = [0] * n
    coeffs[:len(binary)] = binary
    return R(coeffs)

def OneOneMapping(h_value):
    chunk = n // (k ** 2)
    return [BinaryToRing(h_value[i: i + chunk]) for i in range(0, n, chunk)]

def H(ID):
    h_bytes = self._h(ID, 32) # 256 bits = 32 bytes
    h_value = []
    for byte in h_bytes:      
        for bit in range(7, -1, -1):   
            h_value.append((byte >> bit) & 1)
        
    return self.OneOneMapping(h_value)

h_value = [random.randint(0, 1) for _ in range(256)]
print(h_value)
h = OneOneMapping(h_value)
print(h)

# Create a Polynomial Ring