from .hash import sha256_hex


class MerkleTree:
    def __init__(self, leaves: list[bytes]):
        self.leaves = leaves if leaves else [b""]
        n = len(self.leaves)
        if n > 1 and (n & (n - 1)) != 0:
            next_pow2 = 1 << (n - 1).bit_length()
            self.leaves.extend([b""] * (next_pow2 - n))
        self.tree = self._build(self.leaves)

    def _build(self, leaves: list[bytes]) -> list[list[str]]:
        layer = [sha256_hex(leaf) for leaf in leaves]
        tree = [layer]
        while len(layer) > 1:
            nxt = []
            for i in range(0, len(layer), 2):
                combined = layer[i] + layer[i + 1]
                nxt.append(sha256_hex(combined.encode()))
            layer = nxt
            tree.append(layer)
        return tree

    @property
    def root(self) -> str:
        return self.tree[-1][0]

    def get_proof(self, index: int) -> list[dict]:
        proof = []
        for layer in self.tree[:-1]:
            is_right = index % 2
            sibling = index + 1 if not is_right else index - 1
            if sibling < len(layer):
                proof.append({"hash": layer[sibling], "position": "right" if not is_right else "left"})
            index //= 2
        return proof

    @staticmethod
    def verify_proof(leaf: bytes, proof: list[dict], root: str) -> bool:
        current = sha256_hex(leaf)
        for p in proof:
            combined = (p["hash"] + current) if p["position"] == "left" else (current + p["hash"])
            current = sha256_hex(combined.encode())
        return current == root


def build_transaction_merkle(tx_hashes: list[str]) -> str:
    if not tx_hashes:
        return sha256_hex(b"empty")
    leaves = [bytes.fromhex(h) if len(h) == 64 else h.encode() for h in tx_hashes]
    return MerkleTree(leaves).root
