## Setting Up a Python Virtual Environment (macOS)

Follow these steps to create and activate an isolated virtual environment for this project:

1. **Open your Terminal.**

2. **Navigate to the project directory:**
   Use the `cd` command to move into your project's root folder.
   cd path/to/your/project/folder

3. **Create the virtual environment:**
   Run the following command. The second `venv` is the name of the folder that will be created. You can name it whatever you like (e.g., `.venv` or `env`), but `venv` is the standard convention.
   python3 -m venv venv

4. **Activate the virtual environment:**
   Before you install any packages or run the project, you must activate the environment.
   source venv/bin/activate

   *Note: Once activated, you should see `(venv)` appear at the beginning of your terminal prompt.*

5. **Install project dependencies (Optional but recommended):**
   With the environment active, install the required packages using pip.
   pip install -r requirements.txt

6. **Run the app**
   streamlit run app.py

7. **Deactivate the environment:**
   When you are done working on the project, you can exit the virtual environment by simply running:
   deactivate