from math import isqrt


def find_primes(n):
    """Return a list of all prime numbers between 1 and n (inclusive).

    Args:
        n (int): The upper bound. Must be non-negative.

    Returns:
        list: All prime numbers in [1, n].

    Raises:
        ValueError: If n is negative.
    """
    if n < 0:
        raise ValueError("n must be non-negative")

    if n < 2:
        return []

    sieve = bytearray(b'\x01') * ((n + 1) // 2)
    sieve[0] = 0  # 1 is not prime

    limit = isqrt(n)
    for p in range(3, limit + 1, 2):
        if sieve[p // 2]:
            start = (p * p) // 2
            count = (len(sieve) - 1 - start) // p + 1
            sieve[start::p] = b'\x00' * count

    return [2] + [2 * i + 1 for i in range(1, len(sieve)) if sieve[i]]
