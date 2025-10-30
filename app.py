import streamlit as st
import pandas as pd
import logging
import io
import sys

# --- Logger Setup ---
# Configure logging to write to a file and to the console (stdout)
# This ensures logs are visible in the console and saved to 'allocation.log'
# Docker will automatically capture the stdout stream.
try:
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler("allocation.log", mode='a'),
                            logging.StreamHandler(sys.stdout) # Stream to console
                        ])
except Exception as e:
    print(f"Error setting up logging: {e}")

def to_csv(df):
    """Converts a DataFrame to a CSV string (UTF-8 encoded) for download."""
    try:
        # Use io.StringIO to create an in-memory text buffer
        output = io.StringIO()
        df.to_csv(output, index=False)
        # Get the string value and encode it to utf-8 bytes
        return output.getvalue().encode('utf-8')
    except Exception as e:
        logging.error(f"Error converting DataFrame to CSV: {e}", exc_info=True)
        st.error(f"Could not prepare file for download: {e}")
        return b"" # Return empty bytes on failure

def calculate_preference_stats(df, faculty_cols):
    """
    Calculates the faculty preference statistics from the input data.
    Counts how many times each faculty was ranked as 1st, 2nd, 3rd, etc.
    """
    try:
        n_faculties = len(faculty_cols)
        stats_rows = []
        logging.info("Calculating preference statistics...")

        for fac_col in faculty_cols:
            row = {'Fac': fac_col}
            # Get value counts for preference ranks (1 to n)
            # This counts occurrences of each rank (1, 2, ..., n) in the faculty's column
            fac_counts = df[fac_col].value_counts().to_dict()
            
            for i in range(1, n_faculties + 1):
                # Get the count for rank 'i', default to 0 if not present
                row[f'Count Pref {i}'] = fac_counts.get(i, 0)
            
            stats_rows.append(row)
        
        stats_df = pd.DataFrame(stats_rows)
        
        # Ensure columns are in the correct order: Fac, Count Pref 1, Count Pref 2, ...
        cols = ['Fac'] + [f'Count Pref {i}' for i in range(1, n_faculties + 1)]
        stats_df = stats_df[cols]
        
        logging.info("Successfully calculated preference stats.")
        return stats_df
    except Exception as e:
        logging.error(f"Error in calculate_preference_stats: {e}", exc_info=True)
        # Re-raise the exception to be caught by the main processing block
        raise

def perform_allocation(df, faculty_cols):
    """
    Performs the main student-to-faculty allocation logic based on:
    1. Preference Rank (1 to n)
    2. Faculty Order (mod n cycle)
    3. Student CGPA (descending)
    """
    try:
        # 1. Sort students by CGPA (descending)
        sorted_df = df.sort_values(by='CGPA', ascending=False)
        sorted_students = sorted_df.to_dict('records')
        
        # 2. Get faculty list
        faculty_list = faculty_cols
        n_faculties = len(faculty_list)
        
        # 3. Initialize tracking structures
        faculty_alloc_count = {fac: 0 for fac in faculty_list}
        allocated_student_rolls = set() # To track who has been allocated
        final_allocation_list = []      # To build the output dataframe
        
        logging.info(f"Starting allocation for {len(sorted_students)} students and {n_faculties} faculties.")

        # 4. Main allocation loop
        # Iterate by preference rank (1st choice, 2nd choice, ...)
        for pref_rank in range(1, n_faculties + 1):
            
            # Iterate through faculties in their column order (the "mod n" cycle)
            for current_faculty in faculty_list:
                
                # Find the highest-CGPA, unallocated student who wants this faculty at this rank
                for student in sorted_students:
                    roll = student['Roll']
                    # Skip if student is already allocated
                    if roll in allocated_student_rolls:
                        continue
                    
                    # Check if this student's pref_rank matches the current_faculty
                    faculty_at_pref = None
                    try:
                        # Find the faculty name (key) whose value matches the current pref_rank
                        for fac_col in faculty_list:
                            # Convert preference to numeric, coercing errors to NaN
                            student_pref_val = pd.to_numeric(student[fac_col], errors='coerce')
                            if student_pref_val == pref_rank:
                                faculty_at_pref = fac_col
                                break
                    except Exception as e:
                        logging.warning(f"Could not parse preference for student {roll}, faculty {fac_col}. Value: {student[fac_col]}. Error: {e}")
                        continue # Skip to next student
                        
                    # If the student's preference matches the current faculty
                    if faculty_at_pref == current_faculty:
                        
                        # 5. Allocate this student
                        allocated_student_rolls.add(roll)
                        faculty_alloc_count[current_faculty] += 1
                        
                        # Create a record for the final output
                        alloc_record = {
                            'Roll': roll,
                            'Name': student['Name'],
                            'Email': student['Email'],
                            'CGPA': student['CGPA'],
                            'Allocated': current_faculty,
                            'Preference_Rank_Allocated': pref_rank # For debugging
                        }
                        final_allocation_list.append(alloc_record)
                        
                        # Break from the inner student-loop to move to the next faculty
                        break 
        
        # 6. Check for unallocated students
        unallocated_count = len(sorted_students) - len(allocated_student_rolls)
        if unallocated_count > 0:
            logging.warning(f"{unallocated_count} students remain unallocated.")
            # Add unallocated students to the list for visibility
            for student in sorted_students:
                if student['Roll'] not in allocated_student_rolls:
                     alloc_record = {
                            'Roll': student['Roll'],
                            'Name': student['Name'],
                            'Email': student['Email'],
                            'CGPA': student['CGPA'],
                            'Allocated': 'UNALLOCATED', # Mark as UNALLOCATED
                            'Preference_Rank_Allocated': -1
                        }
                     final_allocation_list.append(alloc_record)

        logging.info("Allocation complete.")
        logging.info(f"Faculty Counts (Final): {faculty_alloc_count}")
        
        # 7. Create final DataFrame
        alloc_df = pd.DataFrame(final_allocation_list)
        
        # Select and reorder final columns as requested
        output_cols = ['Roll', 'Name', 'Email', 'CGPA', 'Allocated']
        # Add the debug column if it exists
        if 'Preference_Rank_Allocated' in alloc_df.columns:
             output_cols.append('Preference_Rank_Allocated')
             
        final_alloc_df = alloc_df[output_cols]
        
        return final_alloc_df

    except Exception as e:
        logging.error(f"Error in perform_allocation: {e}", exc_info=True)
        raise # Re-raise the exception

def process_file(uploaded_file):
    """Main processing function to read, validate, and process the uploaded file."""
    try:
        logging.info(f"Processing uploaded file: {uploaded_file.name}")
        # Read the CSV file into a pandas DataFrame
        df = pd.read_csv(uploaded_file)
        
        # 1. Dynamically find faculty columns (Req 1)
        try:
            # Find the integer index of the 'CGPA' column
            cgpa_index = df.columns.get_loc('CGPA')
            # Get all column names *after* 'CGPA'
            faculty_cols = df.columns[cgpa_index + 1:].tolist()
            if not faculty_cols:
                raise ValueError("No faculty columns found after 'CGPA' column.")
            logging.info(f"Found {len(faculty_cols)} faculties: {faculty_cols}")
        except KeyError:
            # This handles if 'CGPA' column itself is missing
            logging.error("Input CSV must contain a 'CGPA' column.")
            raise ValueError("Input CSV must contain a 'CGPA' column.")
        
        # 2. Calculate preference stats (Output B)
        stats_df = calculate_preference_stats(df, faculty_cols)
        
        # 3. Perform allocation (Output A) (Req 2 & 3A)
        alloc_df = perform_allocation(df, faculty_cols)
        
        return alloc_df, stats_df
        
    except Exception as e:
        # Catch any other errors (file read, processing)
        logging.error(f"Error reading or processing file: {e}", exc_info=True)
        raise # Re-raise to be caught by the Streamlit UI

# --- Streamlit UI (Req 1) ---

st.set_page_config(layout="wide")
st.title("BTP/MTP Faculty Allocation System")

# Sidebar for instructions
st.sidebar.header("Instructions")
st.sidebar.markdown("""
1.  **Upload** your student preferences CSV file.
2.  The file must contain columns: `Roll`, `Name`, `Email`, `CGPA`, followed by one column for each faculty.
3.  The values *in* the faculty columns must be the preference rank (e.g., 1, 2, 3...).
4.  The application will generate two downloadable files:
    * `output_allocation.csv`: The final allocation for each student.
    * `fac_preference_count.csv`: Statistics on faculty preferences.
""")
st.sidebar.header("Run (Req 3)")
st.sidebar.markdown("""
**Without Docker:**
```bash
pip install -r requirements.txt
streamlit run app.py
```

**With Docker:**
```bash
docker-compose up --build
```
""")
st.sidebar.header("Logs (Req 4)")
st.sidebar.info("Application logs are being written to `allocation.log` and the console.")

# Main page for file upload
uploaded_file = st.file_uploader("Upload Student Preferences CSV", type=["csv"])

if uploaded_file is not None:
    # Use try-except block to catch all errors during processing (Req 5)
    try:
        # Process the file
        alloc_df, stats_df = process_file(uploaded_file)
        
        st.success("File processed successfully!")
        
        # --- Display Output A: Allocations (Req 3A) ---
        st.header("Student Allocations")
        st.dataframe(alloc_df)
        st.download_button(
            label="Download Allocations (output_allocation.csv)",
            data=to_csv(alloc_df[['Roll', 'Name', 'Email', 'CGPA', 'Allocated']]), # Only download requested columns
            file_name="output_allocation.csv",
            mime="text/csv",
        )
        
        st.divider()
        
        # --- Display Output B: Faculty Stats (Req 3B) ---
        st.header("Faculty Preference Statistics")
        st.dataframe(stats_df)
        st.download_button(
            label="Download Stats (fac_preference_count.csv)",
            data=to_csv(stats_df),
            file_name="fac_preference_count.csv",
            mime="text/csv",
        )
        
    except Exception as e:
        # Log the error and show a user-friendly message
        logging.error(f"Failed to process file: {e}", exc_info=True)
        st.error(f"An error occurred: {e}. Please check the logs or your input file format.")
        st.exception(e) # Display the full exception in the UI for debugging

else:
    st.info("Please upload the input CSV file to begin.")
