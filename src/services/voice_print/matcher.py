from typing import List, Tuple
import numpy as np


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = a.flatten()
    b = b.flatten()
    dot_product = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(dot_product / (norm_a * norm_b))


def cosine_similarity_batch(target: np.ndarray, vectors: List[np.ndarray]) -> List[float]:
    target = target.flatten()
    target_norm = np.linalg.norm(target)
    if target_norm == 0:
        return [0.0] * len(vectors)

    similarities = []
    for v in vectors:
        v = v.flatten()
        v_norm = np.linalg.norm(v)
        if v_norm == 0:
            similarities.append(0.0)
        else:
            sim = np.dot(target, v) / (target_norm * v_norm)
            similarities.append(float(sim))
    return similarities


def find_best_match(
    target_embedding: np.ndarray,
    candidate_embeddings: List[Tuple[str, np.ndarray]],
    threshold: float = 0.7,
) -> Tuple[str, float] | None:
    best_score = threshold
    best_id = None

    for id_, embedding in candidate_embeddings:
        score = cosine_similarity(target_embedding, embedding)
        if score > best_score:
            best_score = score
            best_id = id_

    if best_id is not None:
        return best_id, best_score
    return None