import os
from ..modules.modules import ModuleDilithium

try:
    from xoflib import shake256
except ImportError:
    from ..shake.shake_wrapper import shake256


class ML_DSA:
    def __init__(self, parameter_set):
        self.d = parameter_set["d"]
        self.k = parameter_set["k"]
        self.l = parameter_set["l"]
        self.eta = parameter_set["eta"]
        self.tau = parameter_set["tau"]
        self.omega = parameter_set["omega"]
        self.gamma_1 = parameter_set["gamma_1"]
        self.gamma_2 = parameter_set["gamma_2"]
        self.beta = self.tau * self.eta
        self.c_tilde_bytes = parameter_set["c_tilde_bytes"]

        self.M = ModuleDilithium()
        self.R = self.M.ring

        # Use system randomness by default, for deterministic randomness
        # use the method `set_drbg_seed()`
        self.random_bytes = os.urandom

    def set_drbg_seed(self, seed):
        """
        Change entropy source to a DRBG and seed it with provided value.

        Setting the seed switches the entropy source from :func:`os.urandom()`
        to an AES256 CTR DRBG.

        Used for both deterministic versions of Kyber as well as testing
        alignment with the KAT vectors

        Note:
          currently requires pycryptodome for AES impl.
        """
        try:
            from ..drbg.aes256_ctr_drbg import AES256_CTR_DRBG

            self._drbg = AES256_CTR_DRBG(seed)
            self.random_bytes = self._drbg.random_bytes
        except ImportError as e:  # pragma: no cover
            print(f"Error importing AES from pycryptodome: {e = }")
            raise Warning(
                "Cannot set DRBG seed due to missing dependencies, try installing requirements: pip -r install requirements"
            )

    """
    H() uses Shake256 to hash data to 32 and 64 bytes in a
    few places in the code
    """

    @staticmethod
    def _h(input_bytes, length):
        """
        H: B^*  -> B^*
        """
        return shake256(input_bytes).read(length)

    def _expand_matrix_from_seed(self, rho):
        """
        Helper function which generates a element of size
        k x l from a seed `rho`.
        """
        A_data = [[0 for _ in range(self.l)] for _ in range(self.k)]
        for i in range(self.k):
            for j in range(self.l):
                A_data[i][j] = self.R.rejection_sample_ntt_poly(rho, i, j)
        return self.M(A_data)

    def _expand_vector_from_seed(self, rho_prime):
        s1_elements = [
            self.R.rejection_bounded_poly(rho_prime, i, self.eta) for i in range(self.l)
        ]
        s2_elements = [
            self.R.rejection_bounded_poly(rho_prime, i, self.eta)
            for i in range(self.l, self.l + self.k)
        ]

        s1 = self.M.vector(s1_elements)
        s2 = self.M.vector(s2_elements)
        return s1, s2

    def _expand_mask_vector(self, rho, mu):
        elements = [
            self.R.sample_mask_polynomial(rho, i, mu, self.gamma_1)
            for i in range(self.l)
        ]
        return self.M.vector(elements)

    @staticmethod
    def _pack_pk(rho, t1):
        return rho + t1.bit_pack_t1()

    def _pack_sk(self, rho, K, tr, s1, s2, t0):
        s1_bytes = s1.bit_pack_s(self.eta)
        s2_bytes = s2.bit_pack_s(self.eta)
        t0_bytes = t0.bit_pack_t0()
        return rho + K + tr + s1_bytes + s2_bytes + t0_bytes

    def _pack_h(self, h):
        non_zero_positions = [
            [i for i, c in enumerate(poly.coeffs) if c == 1]
            for row in h._data
            for poly in row
        ]
        packed = []
        offsets = []
        for positions in non_zero_positions:
            packed.extend(positions)
            offsets.append(len(packed))

        padding_len = self.omega - offsets[-1]
        packed.extend([0 for _ in range(padding_len)])
        return bytes(packed + offsets)

    def _pack_sig(self, c_tilde, z, h):
        return c_tilde + z.bit_pack_z(self.gamma_1) + self._pack_h(h)

    def _unpack_pk(self, pk_bytes):
        rho, t1_bytes = pk_bytes[:32], pk_bytes[32:]
        t1 = self.M.bit_unpack_t1(t1_bytes, self.k, 1)
        return rho, t1

    def _unpack_sk(self, sk_bytes):
        if self.eta == 2:
            s_bytes = 96
        else:
            s_bytes = 128
        s1_len = s_bytes * self.l
        s2_len = s_bytes * self.k
        t0_len = 416 * self.k
        if len(sk_bytes) != 2 * 32 + 64 + s1_len + s2_len + t0_len:
            raise ValueError("SK packed bytes is of the wrong length")

        # Split bytes between seeds and vectors
        sk_seed_bytes, sk_vec_bytes = sk_bytes[:128], sk_bytes[128:]

        # Unpack seed bytes
        rho, K, tr = (
            sk_seed_bytes[:32],
            sk_seed_bytes[32:64],
            sk_seed_bytes[64:128],
        )

        # Unpack vector bytes
        s1_bytes = sk_vec_bytes[:s1_len]
        s2_bytes = sk_vec_bytes[s1_len : s1_len + s2_len]
        t0_bytes = sk_vec_bytes[-t0_len:]

        # Unpack bytes to vectors
        s1 = self.M.bit_unpack_s(s1_bytes, self.l, 1, self.eta)
        s2 = self.M.bit_unpack_s(s2_bytes, self.k, 1, self.eta)
        t0 = self.M.bit_unpack_t0(t0_bytes, self.k, 1)

        return rho, K, tr, s1, s2, t0

    def _unpack_h(self, h_bytes):
        offsets = [0] + list(h_bytes[-self.k :])
        non_zero_positions = [
            list(h_bytes[offsets[i] : offsets[i + 1]]) for i in range(self.k)
        ]

        matrix = []
        for poly_non_zero in non_zero_positions:
            coeffs = [0 for _ in range(256)]
            for non_zero in poly_non_zero:
                coeffs[non_zero] = 1
            matrix.append([self.R(coeffs)])
        return self.M(matrix)

    def _unpack_sig(self, sig_bytes):
        c_tilde = sig_bytes[: self.c_tilde_bytes]
        z_bytes = sig_bytes[self.c_tilde_bytes : -(self.k + self.omega)]
        h_bytes = sig_bytes[-(self.k + self.omega) :]

        z = self.M.bit_unpack_z(z_bytes, self.l, 1, self.gamma_1)
        h = self._unpack_h(h_bytes)
        return c_tilde, z, h

    def _keygen_internal(self, zeta):
        """
        Generates a public-private key pair from a seed following
        Algorithm 6 (FIPS 204)
        """
        # Expand with an XOF (SHAKE256)
        seed_domain_sep = zeta + bytes([self.k]) + bytes([self.l])
        seed_bytes = self._h(seed_domain_sep, 128)

        # Split bytes into suitable chunks
        rho, rho_prime, K = seed_bytes[:32], seed_bytes[32:96], seed_bytes[96:]

        # Generate matrix A ∈ R^(kxl) in the NTT domain
        A_hat = self._expand_matrix_from_seed(rho)

        # Generate the error vectors s1 ∈ R^l, s2 ∈ R^k
        s1, s2 = self._expand_vector_from_seed(rho_prime)

        # Matrix multiplication
        s1_hat = s1.to_ntt()
        t = (A_hat @ s1_hat).from_ntt() + s2

        t1, t0 = t.power_2_round(self.d)

        # Pack up the bytes
        pk = self._pack_pk(rho, t1)
        tr = self._h(pk, 64)
        sk = self._pack_sk(rho, K, tr, s1, s2, t0)

        return pk, sk
    
    def BinaryToRing(self, binary):
        coeffs = [0] * 256
        #coeffs[:len(binary)] = binary
        for i in range(len(binary)):
            coeffs[i] = binary[i] * pow(-1, i)
        return self.R(coeffs).to_ntt()

    def OneOneMapping(self, h_value): 
        chunk = 256 // (self.k ** 2)
    
        # k * k 條多項式
        polys = [
            self.BinaryToRing(h_value[i: i + chunk])
            for i in range(0, 256, chunk)
        ]
    
        # Reshape 成 k-by-k matrix
        matrix = [
            polys[i * self.k: (i + 1) * self.k]
            for i in range(self.k)
        ]

        return self.M(matrix)
    
    def H(self, ID):
        h_bytes = self._h(ID, 32) # 256 bits = 32 bytes
        h_value = []
        for byte in h_bytes:      
            for bit in range(7, -1, -1):   
                h_value.append((byte >> bit) & 1)
        
        return self.OneOneMapping(h_value)

    def _sign_internal(self, sk_bytes, m, ID, rnd, external_mu=False):
        """
        Deterministic algorithm to generate a signature for a formatted message
        M' following Algorithm 7 (FIPS 204)

        When `external_mu` is `True`, the message `m` is interpreted instead as
        the pre-hashed message `mu = prehash_external_mu()`
        """
        # unpack the secret key
        rho, K, tr, s1, s2, t0 = self._unpack_sk(sk_bytes)

        # Precompute NTT representation
        s1_hat = s1.to_ntt()
        s2_hat = s2.to_ntt()
        t0_hat = t0.to_ntt()

        # Generate matrix A ∈ R^(kxl) in the NTT domain
        A_hat = self._expand_matrix_from_seed(rho)
        M_hat = self.H(bytes(ID))

        # Set seeds and nonce (kappa)
        if external_mu:
            mu = m
        else:
            mu = self._h(tr + m, 64)
        rho_prime = self._h(K + rnd + mu, 64)

        kappa = 0
        alpha = self.gamma_2 << 1
        while True:
            y = self._expand_mask_vector(rho_prime, kappa)
            y_hat = y.to_ntt()
            w = (A_hat @ y_hat).from_ntt()

            # increment the nonce
            kappa += self.l

            # NOTE: there is an optimisation possible where both the high and
            # low bits of w are extracted here, which speeds up some checks
            # below and requires the use of make_hint_optimised() -- to see the
            # implementation of this, look at the signing algorithm for
            # dilithium. We include this slower version to mirror the FIPS 204
            # document precisely.
            # Extract out only the high bits
            w1 = w.high_bits(alpha)
            H_ID_w1 = (M_hat @ w1.to_ntt()).from_ntt()
            #print(H_ID_w1)

            # Create challenge polynomial
            w1_bytes = H_ID_w1.bit_pack_w(self.gamma_2)
            #w1_bytes = w1.bit_pack_w(self.gamma_2)
            c_tilde = self._h(mu + w1_bytes, self.c_tilde_bytes)
            c = self.R.sample_in_ball(c_tilde, self.tau)
            c_hat = c.to_ntt()

            # NOTE: unlike FIPS 204 we start again as soon as a vector
            # fails the norm bound to reduce any unneeded computations.
            c_s1 = s1_hat.scale(c_hat).from_ntt()
            z = y + c_s1
            if z.check_norm_bound(self.gamma_1 - self.beta):
                continue

            c_s2 = s2_hat.scale(c_hat).from_ntt()
            r0 = (w - c_s2).low_bits(alpha)
            if r0.check_norm_bound(self.gamma_2 - self.beta):
                continue

            c_t0 = t0_hat.scale(c_hat).from_ntt()
            if c_t0.check_norm_bound(self.gamma_2):
                continue

            h = (-c_t0).make_hint(w - c_s2 + c_t0, alpha)
            if h.sum_hint() > self.omega:
                continue

            return self._pack_sig(c_tilde, z, h)

    def _verify_internal(self, pk_bytes, m, sig_bytes, ID):
        """
        Internal function to verify a signature sigma for a formatted message M'
        following Algorithm 8 (FIPS 204)
        """
        rho, t1 = self._unpack_pk(pk_bytes)
        c_tilde, z, h = self._unpack_sig(sig_bytes)

        if h.sum_hint() > self.omega:
            return False

        if z.check_norm_bound(self.gamma_1 - self.beta):
            return False

        A_hat = self._expand_matrix_from_seed(rho)

        tr = self._h(pk_bytes, 64)
        mu = self._h(tr + m, 64)
        c = self.R.sample_in_ball(c_tilde, self.tau)

        # Convert to NTT for computation
        c = c.to_ntt()
        z = z.to_ntt()

        t1 = t1.scale(1 << self.d)
        t1 = t1.to_ntt()

        Az_minus_ct1 = (A_hat @ z) - t1.scale(c)
        Az_minus_ct1 = Az_minus_ct1.from_ntt()

        w_prime = h.use_hint(Az_minus_ct1, 2 * self.gamma_2)
        M_hat = self.H(bytes(ID))
        H_ID_w_prime = (M_hat @ w_prime.to_ntt()).from_ntt()
        w_prime_bytes = H_ID_w_prime.bit_pack_w(self.gamma_2)
        #w_prime_bytes = w_prime.bit_pack_w(self.gamma_2)

        return c_tilde == self._h(mu + w_prime_bytes, self.c_tilde_bytes)

    def keygen(self):
        """
        Generates a public-private key pair following
        Algorithm 1 (FIPS 204)
        """
        zeta = self.random_bytes(32)
        pk, sk = self._keygen_internal(zeta)
        return pk, sk

    def key_derive(self, seed):
        """
        Derive a verification key and corresponding signing key
        following the approach from Section 6.1 (FIPS 204)
        with storage of the ``seed`` value for later expansion.

        ``seed`` is a byte-encoded concatenation of the ``xi`` value.

        :return: Tuple with verification key and signing key.
        :rtype: tuple(bytes, bytes)
        """
        if len(seed) != 32:
            raise ValueError("The seed must be 32 bytes long")

        pk, sk = self._keygen_internal(seed)
        return (pk, sk)

    def sign(self, sk_bytes, m, ID, ctx=b"", deterministic=False):
        """
        Generates an ML-DSA signature following
        Algorithm 2 (FIPS 204)
        """
        if len(ctx) > 255:
            raise ValueError(
                f"ctx bytes must have length at most 255, ctx has length {len(ctx) = }"
            )

        if deterministic:
            rnd = bytes([0] * 32)
        else:
            rnd = self.random_bytes(32)

        # Format the message using the context
        m_prime = bytes([0]) + bytes([len(ctx)]) + ctx + m

        # Compute the signature of m_prime
        sig_bytes = self._sign_internal(sk_bytes, m_prime, ID,rnd)
        return sig_bytes

    def verify(self, pk_bytes, m, sig_bytes, ID,ctx=b""):
        """
        Verifies a signature sigma for a message M following
        Algorithm 3 (FIPS 204)
        """
        if len(ctx) > 255:
            raise ValueError(
                f"ctx bytes must have length at most 255, ctx has length {len(ctx) = }"
            )

        # Format the message using the context
        m_prime = bytes([0]) + bytes([len(ctx)]) + ctx + m

        return self._verify_internal(pk_bytes, m_prime, sig_bytes, ID)

    """
    The following external mu functions are not in FIPS 204, but are in
    Appendix D of the following IETF draft and are included for experimentation
    for researchers and engineers

    https://datatracker.ietf.org/doc/html/draft-ietf-lamps-dilithium-certificates-07
    """

    def prehash_external_mu(self, pk_bytes, m, ctx=b""):
        """
        Prehash the message `m` with context `ctx` together with
        the public key. For use with `sign_external_mu()`
        """
        # Ensure the length of the context is as expected
        if len(ctx) > 255:
            raise ValueError(
                f"ctx bytes must have length at most 255, ctx has length {len(ctx) = }"
            )

        # Format the message using the context
        m_prime = bytes([0]) + bytes([len(ctx)]) + ctx + m

        # Compute mu by hashing the public key into the message
        tr = self._h(pk_bytes, 64)
        mu = self._h(tr + m_prime, 64)

        return mu

    def sign_external_mu(self, sk_bytes, mu, deterministic=False):
        """
        Generates an ML-DSA signature of a message given the prehash
        mu = H(H(pk), M')
        """
        # Ensure the length of the context is as expected
        if len(mu) != 64:
            raise ValueError(
                f"mu bytes must have length 64, mu has length {len(mu) = }"
            )

        if deterministic:
            rnd = bytes([0] * 32)
        else:
            rnd = self.random_bytes(32)

        # Compute the signature given external mu, we set the external_mu
        # to True
        sig_bytes = self._sign_internal(sk_bytes, mu, rnd, external_mu=True)
        return sig_bytes
