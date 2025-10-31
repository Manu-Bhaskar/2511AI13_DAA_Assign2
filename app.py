import streamlit as st
import pandas as pd
import logging
import io
import sys

try:
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        handlers=[
                            logging.FileHandler("allocation.log", mode='a'),
                            logging.StreamHandler(sys.stdout)
                        ])
except Exception as e:
    print(f"Error setting up logging: {e}")

def to_csv(df):
    """Converts a DataFrame to a CSV string (UTF-8 encoded) for download."""
    try:
        output = io.StringIO()
        df.to_csv(output, index=False)
        return output.getvalue().encode('utf-8')
    except Exception as e:
        logging.error(f"Error converting DataFrame to CSV: {e}", exc_info=True)
        st.error(f"Could not prepare file for download: {e}")
        return b""

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
            fac_counts = df[fac_col].value_counts().to_dict()
            
            for i in range(1, n_faculties + 1):
                row[f'Count Pref {i}'] = fac_counts.get(i, 0)
            
            stats_rows.append(row)
        
        stats_df = pd.DataFrame(stats_rows)
        
        cols = ['Fac'] + [f'Count Pref {i}' for i in range(1, n_faculties + 1)]
        stats_df = stats_df[cols]
        
        logging.info("Successfully calculated preference stats.")
        return stats_df
    except Exception as e:
        logging.error(f"Error in calculate_preference_stats: {e}", exc_info=True)
        raise

def perform_allocation(df, faculty_cols):
    """
    Performs the main student-to-faculty allocation logic based on:
    1. Preference Rank (1 to n)
    2. Faculty Order (mod n cycle)
    3. Student CGPA (descending)
    """
    try:
        sorted_df = df.sort_values(by='CGPA', ascending=False)
        sorted_students = sorted_df.to_dict('records')
        
        faculty_list = faculty_cols
        n_faculties = len(faculty_list)
        
        faculty_alloc_count = {fac: 0 for fac in faculty_list}
        allocated_student_rolls = set() 
        final_allocation_list = []    
        
        logging.info(f"Starting allocation for {len(sorted_students)} students and {n_faculties} faculties.")

        for pref_rank in range(1, n_faculties + 1):
            
            for current_faculty in faculty_list:
                
                for student in sorted_students:
                    roll = student['Roll']
                    if roll in allocated_student_rolls:
                        continue
                    
                    faculty_at_pref = None
                    try:
                        for fac_col in faculty_list:
                            student_pref_val = pd.to_numeric(student[fac_col], errors='coerce')
                            if student_pref_val == pref_rank:
                                faculty_at_pref = fac_col
                                break
                    except Exception as e:
                        logging.warning(f"Could not parse preference for student {roll}, faculty {fac_col}. Value: {student[fac_col]}. Error: {e}")
                        continue
                        
                    if faculty_at_pref == current_faculty:
                        
                        allocated_student_rolls.add(roll)
                        faculty_alloc_count[current_faculty] += 1
                        
                        alloc_record = {
                            'Roll': roll,
                            'Name': student['Name'],
                            'Email': student['Email'],
                            'CGPA': student['CGPA'],
                            'Allocated': current_faculty,
                            'Preference_Rank_Allocated': pref_rank 
                        }
                        final_allocation_list.append(alloc_record)
                        
                        break 
        
        unallocated_count = len(sorted_students) - len(allocated_student_rolls)
        if unallocated_count > 0:
            logging.warning(f"{unallocated_count} students remain unallocated.")
            for student in sorted_students:
                if student['Roll'] not in allocated_student_rolls:
                     alloc_record = {
                            'Roll': student['Roll'],
                            'Name': student['Name'],
                            'Email': student['Email'],
                            'CGPA': student['CGPA'],
                            'Allocated': 'UNALLOCATED', 
                            'Preference_Rank_Allocated': -1
                        }
                     final_allocation_list.append(alloc_record)

        logging.info("Allocation complete.")
        logging.info(f"Faculty Counts (Final): {faculty_alloc_count}")
        
        alloc_df = pd.DataFrame(final_allocation_list)
        
        output_cols = ['Roll', 'Name', 'Email', 'CGPA', 'Allocated']
        if 'Preference_Rank_Allocated' in alloc_df.columns:
             output_cols.append('Preference_Rank_Allocated')
             
        final_alloc_df = alloc_df[output_cols]
        
        return final_alloc_df

    except Exception as e:
        logging.error(f"Error in perform_allocation: {e}", exc_info=True)
        raise 

def process_file(uploaded_file):
    """Main processing function to read, validate, and process the uploaded file."""
    try:
        logging.info(f"Processing uploaded file: {uploaded_file.name}")
        df = pd.read_csv(uploaded_file)
        
        try:
            cgpa_index = df.columns.get_loc('CGPA')
            faculty_cols = df.columns[cgpa_index + 1:].tolist()
            if not faculty_cols:
                raise ValueError("No faculty columns found after 'CGPA' column.")
            logging.info(f"Found {len(faculty_cols)} faculties: {faculty_cols}")
        except KeyError:
            logging.error("Input CSV must contain a 'CGPA' column.")
            raise ValueError("Input CSV must contain a 'CGPA' column.")
        
        stats_df = calculate_preference_stats(df, faculty_cols)
        
        alloc_df = perform_allocation(df, faculty_cols)
        
        return alloc_df, stats_df
        
    except Exception as e:
        logging.error(f"Error reading or processing file: {e}", exc_info=True)
        raise 


st.set_page_config(layout="wide")
st.title("BTP/MTP Faculty Allocation System")

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

uploaded_file = st.file_uploader("Upload Student Preferences CSV", type=["csv"])

if uploaded_file is not None:
    try:
        alloc_df, stats_df = process_file(uploaded_file)
        
        st.success("File processed successfully!")
        
        st.header("Student Allocations")
        st.dataframe(alloc_df)
        st.download_button(
            label="Download Allocations (output_allocation.csv)",
            data=to_csv(alloc_df[['Roll', 'Name', 'Email', 'CGPA', 'Allocated']]),
            file_name="output_allocation.csv",
            mime="text/csv",
        )
        
        st.divider()
        
        st.header("Faculty Preference Statistics")
        st.dataframe(stats_df)
        st.download_button(
            label="Download Stats (fac_preference_count.csv)",
            data=to_csv(stats_df),
            file_name="fac_preference_count.csv",
            mime="text/csv",
        )
        
    except Exception as e:
        logging.error(f"Failed to process file: {e}", exc_info=True)
        st.error(f"An error occurred: {e}. Please check the logs or your input file format.")
        st.exception(e)

else:
    st.info("Please upload the input CSV file to begin.")
