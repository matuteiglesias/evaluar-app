'''
This file defines the Exercise class.
'''
class Exercise:
    def __init__(self):
        # Initialize exercise properties
        self.prompt = "Write a Python program to calculate the factorial of a number."
        self.solution = '''
        def factorial(n):
            if n == 0:
                return 1
            else:
                return n * factorial(n-1)
        num = int(input("Enter a number: "))
        print("Factorial of", num, "is", factorial(num))
        '''
    def get_prompt(self):
        # Return the exercise prompt
        return self.prompt
    def get_solution(self):
        # Return the exercise solution
        return self.solution