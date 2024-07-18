
names = ["Juan", "Martín", "Anthonny","Jordi", "Viridiana", "Martín"]#--> db 1gb
names_copy = names.copy()

fuit = ("Apple", "Orange", "Donkey") 
my_set =  {"Apple", "Orange", "Donkey","Apple"}

names[0] = "Pablo"
# fuit[0] = "Piña"

# print(names[0])
# print(fuit[0])
# print(my_set)

# names[3] = "Huttman"
# print(names[2])
# print(names[len(names)-1])
# print(names)

names.append("Daniel Perdomo")
names.insert(2, "Leonardo Muñoz")
# delete =  names.pop(0)
# result_martin = names.count("Martín")
# print(result_martin)
# names.remove("Martín")
# names.remove("Martín")
# del names[0]
# print(names)
# print(delete)


# for index in range(len(names)):
#     print(f"Hola ¿qué tal {names[index]}? Chao!!") 


# for num in range(30, 0, -1):
#     print(num)

# for index, value in enumerate(names):
#     print(index, value)

# for name in names:
#     if name.lower() == "martín":
#         names.remove(name)

# print(names)
names_copy.reverse()

print(names)
print(names_copy)

