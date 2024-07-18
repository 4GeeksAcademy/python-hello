import random


# 1. El computador crea el número de 3 digítos con el que va a jugar
# 2. Pedirle al usuario que ingrese el número (user)
# 3. Si acierta el número pero no la posición cuanta como herido
# 4. Si acierta el numero y la posición  muerto
# 5. gana quien complete los tres números 

lista_num = [0,1,2,3,4,5,6,7,8,9]
seleccion_maquina = random.sample(lista_num, 3) 

count = 0

while True: 
    muerto = 0
    herido = 0

    entrada_usuario = input("Ingresa un número de tres dígitos: ")
    
    if len(entrada_usuario) != 3:
        print("El número debe ser de 3 dígitos, ingresa uno nuevamente")
        continue

    seleccion_usuario = []
    for num in entrada_usuario:
        seleccion_usuario.append(int(num))

    for index_m, value_m in enumerate(seleccion_maquina):
        for index_u, value_u in enumerate(seleccion_usuario):
            if index_m == index_u and value_m == value_u:
                muerto = muerto + 1
            elif value_u == value_m:
                herido = herido +1


    count = count+1


    if muerto == 3:
        print("Que bien GANASTE!!!")
        break
    
    print(f"Tienes {muerto} muertos y {herido} heridos\n\n")
    print(f"{count} intentos")