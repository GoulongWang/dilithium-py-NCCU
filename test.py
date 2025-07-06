from dilithium_py.ml_dsa import ML_DSA_44
import random
pk, sk = ML_DSA_44.keygen()
msg = b"test msg"
ID = [random.randint(0, 1) for _ in range(4)]
sig = ML_DSA_44.sign(sk, msg, ID)
assert ML_DSA_44.verify(pk, msg, sig, ID)