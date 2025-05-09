import pandas as pd
import numpy as np
import joblib

"""
This are the values that the model expect ['gender', 'ethnicity', 'income', 'internet_access', 'logging_in',
'quiz_completion', 'last_session_course_unit', 'weighted_grade_point']
They should come as a dictionary.
"""

"""
The changes i made include adding these column 'content_engagement' , 'live_class' and removing these columns 'logging_in',
'quiz_completion' so now the model expects ['gender', 'ethnicity', 'income', 'internet_access','last_session_course_unit', 
'content_engagement', 'live_class', 'weighted_grade_point'] please check the input example for better understanding.
"""

def new_make_prediction(input_data):
    print("======="*20)
    print(input_data)
    # Check if the input is already a DataFrame
    if isinstance(input_data, pd.DataFrame):
        input_df = input_data
    else:
        # Convert the input dictionary to a DataFrame
        # Handle both single-row and list-based dictionaries
        if any(isinstance(v, list) for v in input_data.values()):
            # If any value is a list, transpose the dictionary
            input_df = pd.DataFrame(input_data)
        else:
            # If all values are single items, create DataFrame from a single row
            input_df = pd.DataFrame([input_data])
    
    # Dynamically identify categorical and numerical columns
    categorical_columns = input_df.select_dtypes(include=['object', 'category']).columns.tolist()
    numerical_columns = input_df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    
    # Ensure the input DataFrame has the same column order as the training data
    input_df = input_df[categorical_columns + numerical_columns]
    
    # Load the model
    loaded_model = joblib.load('performance_model.pkl')
    
    # Predict using the model
    prediction = loaded_model.predict(input_df)
    
    print(prediction)
    return prediction  


# input_data = {
#     'gender': ['Male', 'Female', 'Female', 'Male','Male'],
#     'ethnicity': ['Other', 'Other', 'Igbo', 'Hausa','yoruba'],
#     'income': ['NGN 200,000 – NGN 500,000', 'NGN 500,000 and above', 'No income',
#        'NGN 50,000 – NGN 100,000','NGN 200,000 – NGN 500,000'],
#     'internet_access': ['Yes', 'No',"yes","no","yes"],
#     'live_class': [12,16,4,0,20],
#     'content_engagement': [70,80,40,20,100],
#     'last_session_course_unit': [24, 38, 12, 25, 32],
#     'weighted_grade_point': [138, 120, 62, 98, 125]
# }
# print(new_make_prediction(input_data))