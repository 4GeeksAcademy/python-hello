def palindromo(palabra):
    palabra = palabra.replace(" ", "")
    palabra = palabra.lower()
    palabra_inversa = palabra[::-1]

    if palabra == palabra_inversa:
        return True
    else:
        return False


def run():
    palabra = input("Ingresa una palabra: ")
    result = palindromo(palabra)

    if result:
        print("SI, esta palabra es palindromo")
    else:
        print("NO, esta palabra no es un palindromo")



#entry point
if __name__ == "__main__":
    run()


# ana -> ana 
# arepera