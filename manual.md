# Educational Platform User Manual

## Introduction

Welcome to the user manual for the Educational Platform developed by ChatDev. This platform allows students to complete exercises online and receive immediate feedback through an AI-based machine evaluator. The platform also stores all interactions in a database for future reference. This manual will guide you through the installation process and provide instructions on how to use the platform effectively.

## Table of Contents

1. Installation
2. Usage
3. Exercise Completion
4. Viewing Feedback
5. Database Interactions

## 1. Installation

To install the Educational Platform, follow these steps:

1. Ensure that you have Python installed on your system. If not, download and install Python from the official website (https://www.python.org/).

2. Clone the repository containing the platform's source code using the following command:

   ```
   git clone <repository_url>
   ```

3. Navigate to the project directory using the command line.

4. Install the required dependencies by running the following command:

   ```
   pip install -r requirements.txt
   ```

5. Once the dependencies are installed, you are ready to use the Educational Platform.

## 2. Usage

To use the Educational Platform, follow these steps:

1. Open a command prompt or terminal and navigate to the project directory.

2. Run the following command to start the platform:

   ```
   python main.py
   ```

3. Open a web browser and enter the following URL:

   ```
   http://localhost:5000
   ```

4. You will see the exercise prompt displayed on the webpage. Enter your response in the provided text field and click the "Submit" button.

5. The platform will process your response using the AI-based machine evaluator and provide immediate feedback.

6. You can repeat the exercise completion process as many times as needed.

## 3. Exercise Completion

To complete an exercise on the Educational Platform, follow these steps:

1. Access the platform using the steps mentioned in the "Usage" section.

2. Read the exercise prompt displayed on the webpage.

3. Write your solution to the exercise in the provided text field.

4. Click the "Submit" button to submit your response.

5. The platform will process your response and provide immediate feedback based on the AI-based machine evaluator.

## 4. Viewing Feedback

After submitting your response to an exercise, the Educational Platform will provide immediate feedback. To view the feedback, follow these steps:

1. Access the platform using the steps mentioned in the "Usage" section.

2. Complete an exercise by following the steps mentioned in the "Exercise Completion" section.

3. Once you submit your response, the platform will process it and display the evaluated response on the webpage.

4. The evaluated response will indicate whether your solution is correct or incorrect.

5. Review the evaluated response to understand the feedback provided by the AI-based machine evaluator.

6. Use the feedback to improve your understanding and skills in solving similar exercises.

## 5. Database Interactions

The Educational Platform stores all interactions, including student inputs and AI-generated outputs, in a database. To interact with the database, follow these steps:

1. Access the platform using the steps mentioned in the "Usage" section.

2. Complete an exercise by following the steps mentioned in the "Exercise Completion" section.

3. Once you submit your response, the platform will store the interaction in the database.

4. To view the stored interactions, you can access the database directly using a SQLite database viewer or execute SQL queries programmatically.

5. The interactions table in the database contains a single column named "response" that stores the student's response for each exercise.

6. You can use the stored interactions for analysis, tracking progress, or any other purposes related to student learning.

Congratulations! You have successfully installed and learned how to use the Educational Platform. Enjoy completing exercises and improving your skills with immediate feedback.
