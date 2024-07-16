# color = input("Ingresa un color: ")
# color = color.lower()

# print(color)

# if color == "red":
#     print("No me gusta el color")
#         #escribirlo aca
# else:
#     print("Excelente color")


# siento_que_me_atropello_un_tren = True
# me_atropello_un_tren = False


# if siento_que_me_atropello_un_tren:

#     if me_atropello_un_tren:
#         print("No tienes gripe")
        
#     else:
#         print("Tienes gripe")
# else:
#     print("No tienes gripe")


# user = None

# if user is None:
#     print("Usuario no encontrado")
# else:
#     print("Usuario logueado")
    
    
# if "bob" in ['bob','maria','nancy']:
#     print("Conseguimos a bob")
# else:
#     print("Se perdio")
    
    
# print(5> 4 and 5<4)

# print(5< 4 or 5<4 or 10> 5)

# age = 60

# if age < 16:  print("No puedes hacer nada")

# if age < 18:  print("A estas alturas, ya sabemos que es mayor de 15 porque si no, no hubiese ingresado a la primera condición")

# if age < 21:  print("Si el algoritmo ingresa aquí, sabemos que es mayor de 17 ")

# else: print("Si el algoritmo ingresa aquí, sabemos que es mayor de 20")
saldo = 10000000000

while True:
    print("""
        1. Suma
        2. Resta
        3. Salir
    """)
    
    opc = int(input("Elige una opción: "))
    
    if opc == 1:
        num1 = float(input("Ingresa el primer número a sumar: "))
        num2 = float(input("Ingresa el segundo número a sumar: "))
        
        print(f"\nEl resultado es --> {num1+num2}")
        
    elif opc == 2:
        pass
    
    elif opc == 3:
        break
    
    