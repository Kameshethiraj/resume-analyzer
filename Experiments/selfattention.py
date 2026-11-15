import numpy as np

# Three tokens:
# John, works, Infosys

X = np.array([
    [0.2, 0.8],
    [0.6, 0.4],
    [0.9, 0.1]
])

# Toy weight matrices
WQ = np.array([
    [0.5, 0.2],
    [0.1, 0.7]
])

WK = np.array([
    [0.4, 0.3],
    [0.2, 0.6]
])

WV = np.array([
    [0.3, 0.5],
    [0.7, 0.1]
])


# Step 1: Create Q, K, V
Q = X @ WQ
K = X @ WK
V = X @ WV

print("Q:")
print(Q)

print("\nK:")
print(K)

print("\nV:")
print(V)


# Step 2: Calculate attention scores
scores = Q @ K.T

print("\nAttention Scores:")
print(scores)


# Step 3: Scale the scores
d_k = K.shape[1]

scaled_scores = scores / np.sqrt(d_k)

print("\nScaled Scores:")
print(scaled_scores)


# Step 4: Softmax
def softmax(x):
    exp_x = np.exp(x - np.max(x, axis=-1, keepdims=True))
    return exp_x / np.sum(exp_x, axis=-1, keepdims=True)


attention_weights = softmax(scaled_scores)

print("\nAttention Weights:")
print(attention_weights)


# Step 5: Weighted combination of Values
output = attention_weights @ V

print("\nSelf-Attention Output:")
print(output)