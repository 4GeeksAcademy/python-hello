names = ["Juan", "Martín", "Anthonny","Jordi", "Viridiana", "Martín"]

def suma(num1=0, num2=0):
    result =  num1 + num2
    return result


print(suma(52, 8444))


def saludar(name, lastname):
    result = f"Hola ¿qué tal {name} {lastname}? Byee!"
    return result


print(saludar(lastname="Vásquez", name="Deimian"))


def multi(*args):
    total = 1

    for num in args:
        total = num*total
    return total



def resta(num1, num2):
    return num1 -num2

suma_dos = lambda num1, num2: num1 + num2
# print(suma_dos(50,51))


saludos = list(map(lambda un_nombre: f"Hola, {un_nombre}", names))
print(saludos)


def filter_martin(name):
    return name != "Martín"


names_filter = list(filter(filter_martin , names ))
print(names_filter)


count = 0

while count < 20:
    print(count)
    count+=1
    