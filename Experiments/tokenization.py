import tiktoken


text = "John is is a Python developer"


encoding = tiktoken.get_encoding("o200k_base")


tokens = encoding.encode(text)


print("Text:")
print(text)

print("\nToken IDs:")
print(tokens)

print("\nNumber of tokens:")
print(len(tokens))

print("\nDecoded tokens:")

for token_id in tokens:
    token = encoding.decode([token_id])
    print(token_id, "->", repr(token))