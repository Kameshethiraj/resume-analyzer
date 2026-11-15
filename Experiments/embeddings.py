import numpy as np


# Imagine these are token IDs
token_ids = {
    "Python": 0,
    "Java": 1,
    "Database": 2,
    "RabbitMQ": 3
}


# A tiny embedding matrix.
# Real models use much larger dimensions.
embedding_matrix = np.array([
    [0.9, 0.8, 0.1],   # Python
    [0.8, 0.7, 0.2],   # Java
    [0.1, 0.2, 0.9],   # Database
    [0.2, 0.3, 0.8]    # RabbitMQ
])


for word, token_id in token_ids.items():

    embedding = embedding_matrix[token_id]

    print(f"{word} (ID={token_id})")
    print(embedding)
    print()