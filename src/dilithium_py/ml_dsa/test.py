from dilithium_py.polynomials.polynomials_generic import PolynomialRing
from dilithium_py.modules.modules_generic import Module
from dilithium_py.ml_dsa import ML_DSA_44
from dilithium_py.modules.modules import ModuleDilithium
import random

# Create ONE global ModuleDilithium instance to use consistently
M = ModuleDilithium()
R = M.ring

q = 8380417
n = 256
k = 4

def BinaryToRing(binary):
    coeffs = [0] * n
    coeffs[:len(binary)] = binary
    return R(coeffs).to_ntt()

def OneOneMapping(h_value): 
    chunk = n // (k ** 2)
    
    # k * k 條多項式
    polys = [
        BinaryToRing(h_value[i: i + chunk])
        for i in range(0, n, chunk)
    ]
    
    # Reshape 成 k-by-k matrix
    matrix = [
        polys[i * k: (i + 1) * k]
        for i in range(k)
    ]

    # Use the SAME ModuleDilithium instance every time
    return M(matrix)
    
def H(ID):
    h_bytes = ML_DSA_44._h(ID, 32) # 256 bits = 32 bytes
    h_value = []
    for byte in h_bytes:      
        for bit in range(7, -1, -1):   
            h_value.append((byte >> bit) & 1)
        
    return OneOneMapping(h_value)

ID = [random.randint(0, 1) for _ in range(8)]
matrix1 = H(bytes(ID))

ID2 = [random.randint(0, 1) for _ in range(8)]
matrix2 = H(bytes(ID2))

print("H(ID) = ", matrix1)
print("H(ID2) = ", matrix2)
print("matrix1 @ matrix2 =", matrix1 @ matrix2)

#test NTT
# R = ML_DSA_44.R
# f = R.random_element()
# print("f = ", f)
# print("NTT(f) = ", f.to_ntt())
# g = R.random_element()
# print("g = ", g)
# print("NTT(g) = ", g.to_ntt())
# print("fg = ", (f.to_ntt() * g.to_ntt()).from_ntt())