import pandas as pd
import joblib
from typing import Dict, Any

from utils.login_manager import LoginManager

"""
This are the values that the model expect ['gender', 'ethnicity', 'income', 'internet_access', 'logging_in',
'quiz_completion', 'last_session_course_unit', 'weighted_grade_point']
They should come as a dictionary.
"""
#!TODO weighted_grade_point to total_quality_points



loaded_model = joblib.load('performance_model.pkl')

def make_prediction_babatunde(input_data):
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
    
    
    # Predict using the model
    prediction = loaded_model.predict(input_df)
    
    print(prediction)
    return prediction  


def make_prediction1(input_data: Dict[str, Any],user) -> Any:

    input_data['logging_in'] = LoginManager.determine_logging_behavior(user)

    print(input_data)

    # Convert the input dictionary to a DataFrame
    input_df = pd.DataFrame([input_data])

    print(input_df)
    
    # Dynamically identify categorical and numerical columns
    categorical_columns = input_df.select_dtypes(include=['object', 'category']).columns.tolist()

    print("CATEGORICAL COLUMNS :: ",categorical_columns)
    numerical_columns = input_df.select_dtypes(include=['int64', 'float64']).columns.tolist()

    print("NUMERICAL COLUMNS :: ",numerical_columns)
    
    # Ensure the input DataFrame has the same column order as the training data
    input_df = input_df[categorical_columns + numerical_columns]
    
    print("POST INPUT DIF :: ",input_df)    
    # Predict using the model
    prediction = loaded_model.predict(input_df)
    
    return prediction


def make_prediction(input_data: Dict[str, Any], user) -> Any:

    # Assuming the 'LoginManager' works properly and provides a valid behavior
    input_data['logging_in'] = LoginManager.determine_logging_behavior(user)

    print("Input data after adding 'logging_in': ", input_data)

    # Convert the input dictionary to a DataFrame
    input_df = pd.DataFrame([input_data])

    print("Input DataFrame before cleaning: \n", input_df)

    # Handle missing or NaN values:
    # Fill missing categorical columns with a placeholder or mode
    categorical_columns = input_df.select_dtypes(include=['object', 'category']).columns.tolist()
    for col in categorical_columns:
        input_df[col].fillna(input_df[col].mode()[0], inplace=True)  # Fill with the most frequent value

    # For numerical columns, you could either fill NaNs with 0 or the column mean, etc.
    numerical_columns = input_df.select_dtypes(include=['int64', 'float64']).columns.tolist()
    for col in numerical_columns:
        input_df[col].fillna(input_df[col].mean(), inplace=True)  # Fill with the mean of the column
    
    print("DataFrame after filling missing values: \n", input_df)

    # Dynamically identify categorical and numerical columns (for consistency)
    categorical_columns = input_df.select_dtypes(include=['object', 'category']).columns.tolist()
    numerical_columns = input_df.select_dtypes(include=['int64', 'float64']).columns.tolist()


    # Ensure the input DataFrame has the same column order as the training data
    # It is important that the input columns match the model's training columns exactly
    input_df = input_df[categorical_columns + numerical_columns]

    print("Post-processing input for prediction: \n", input_df)

    # Predict using the model
    try:
        prediction = loaded_model.predict(input_df)
        print("Prediction result: ", prediction)
        return prediction
    except Exception as e:
        print(f"Prediction error: {e}")
        return None  # or handle the exception as needed


input_data = {
    'gender': ['Male', 'Female', 'Female', 'Male','Male'],
    'ethnicity': ['Asian', 'Black', 'Hispanic', 'White','yoruba'],
    'income': ['NGN 200,000 – NGN 500,000', 'NGN 500,000 and above', 'No income',
       'NGN 50,000 – NGN 100,000','NGN 200,000 – NGN 500,000'],
    'internet_access': ['Yes', 'No',"yes","no","yes"],
    'logging_in': ['Daily','not often', 'Weekly', 'Monthly', 'Daily'],
    'quiz_completion': ["NO",'yes' ,"Yes", "yes", "No"],
    'last_session_course_unit': [24, 38, 46, 25, 32],
    'weighted_grade_point': [138, 120, 110, 98, 129]
}
# make_prediction_babatunde(input_data)



