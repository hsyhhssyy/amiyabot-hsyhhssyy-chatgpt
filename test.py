def my_decorator(func):
    def wrapper(self, *args, **kwargs):
        return func(self, *args, **kwargs)
    return wrapper

class MyClass:
    def existing_method(self):
        print("This is an existing method.")

def new_method(self):
    print("This is a new method.")

MyClass.new_method = new_method


class My2ndClass(MyClass):
    pass

obj = My2ndClass()

obj.new_method()