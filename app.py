# from Flask import flask
import suma
import os

# print("Hola desde python")

# esto es un comentario
# nombre_apellido 
# Math --> clase

num1 = 2.00
num2 = "3"
# num3 = float(input("Dame un número: "))
# print(num3)
# name = None

# print(num1+ float(num2)+num3)

# print(name)

myArray = ['Juan','John','Steven'] # Lista con índices numéricos
myTuple = ('Juan','John','Steven')
mySet = {'Juan','John','Steven'}


dictionary = {
    "name": "deimian",
    "lastname":"Vásquez"
}

# print(dictionary['name'])


# class Human():
#     #constructor
#     def __init__(self, name, lastname):
#         self.name = name

# human = Human("Deimian", "Vasquez")

# print(Human.__name__)

lastname = "Vásquez"
name = 'Deimian'
lastname3 = """
                Vásquez "Más" largo
                Cómo te digo?
            """

# print(len(lastname2))
# print(lastname2[3])
# print(lastname2[2:9])
# print(lastname2[:9])
# print(lastname2[3:])
# print(lastname2[::-1])

print("Hola ¿qué tal "+name+" "+ lastname+" ?")
print(f"Hola ¿qué tal {name} {lastname} {6*6}?")


print(suma.saludar)
    
# print(os.cpu_count.__str__())
mem=str(os.popen('free -t -m').readlines())
print(mem)