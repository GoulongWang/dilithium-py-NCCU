from dilithium_py.ml_dsa import ML_DSA_44, ML_DSA_65, ML_DSA_87
from dilithium_py.utilities.utils import reduce_mod_pm
from dilithium_py.polynomials.polynomials import PolynomialRingDilithium

import random
# pk, sk = ML_DSA_44.keygen()
# msg = b"test msg"
# ID = [random.randint(0, 1) for _ in range(4)]
# sig = ML_DSA_44.sign(sk, msg, ID)
# assert ML_DSA_44.verify(pk, msg, sig, ID)

#print(reduce_mod_pm(-1, 8380417))
for i in range(100):
    pk, sk = ML_DSA_44.keygen()
    msg = b"test msg"
    ID = [random.randint(0, 1) for _ in range(20)]
    sig = ML_DSA_44.sign(sk, msg, ID)
    assert ML_DSA_44.verify(pk, msg, sig, ID)

for i in range(100):
    pk, sk = ML_DSA_65.keygen()
    msg = b"test msg"
    ID = [random.randint(0, 1) for _ in range(20)]
    sig = ML_DSA_65.sign(sk, msg, ID)
    assert ML_DSA_65.verify(pk, msg, sig, ID)

for i in range(100):
    pk, sk = ML_DSA_87.keygen()
    msg = b"test msg"
    ID = [random.randint(0, 1) for _ in range(20)]
    sig = ML_DSA_87.sign(sk, msg, ID)
    assert ML_DSA_87.verify(pk, msg, sig, ID)

# pk, sk = ML_DSA_87.keygen()
# msg = b"test msg"
# ID = [random.randint(0, 1) for _ in range(4)]
# sig = ML_DSA_87.sign(sk, msg, ID)
# assert ML_DSA_87.verify(pk, msg, sig, ID)
# ring = PolynomialRingDilithium()
# x = ring.gen()
# print(ring)
# f = -1*x**3 - 1 *x**7
# print(f) # PolynomialDilithium
# print(f.to_reduce_mod_pm())

print("ALL GOOD!")