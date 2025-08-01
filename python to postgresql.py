#import pandas for dataset retreival 
#import psycopg2 for database connection
import pandas as pd
import psycopg2 as pg
import psycopg2.extras as extras

# location of the csv file
csv_location = os.getenv('CSV_FILE_PATH')

# use pandas to read the location of the csv file and then store as the a dataframe
# also replace the 'Not Available' and 'unknown' values with NULL values
df = pd.read_csv(csv_location, na_values = ['Not Available', 'unknown'])

#sets each column to lowercase
df.columns = df.columns.str.lower()
#replaces the spaces in each column with underscores
df.columns = df.columns.str.replace(' ', '_')

#creating sets of derived columns
df['discount'] = df['list_price'] * df['discount_percent'] * 0.01
df['discount'] = df['discount'].round(2)
df['sale_price'] = df['list_price'] - df['discount']
df['profit'] = df['sale_price'] - df['cost_price']
df['profit'] = df['profit'].round(2)

#changes datatype of order_date to datetime
df['order_date'] = pd.to_datetime(df['order_date'], format="%Y-%m-%d")

#drops columns from view that are not needed to be shown but are important for the calucation of derived columns
df.drop(columns=['list_price', 'cost_price', 'discount_percent'], inplace=True)

#create a connection varaible with connection parameters to be used when establoshing a connection with posgresql database
conn = pg.connect(
    host=os.getenv('DB_HOST', 'localhost'),
    database=os.getenv('DB_NAME', 'postgres'),
    user=os.getenv('DB_USER', 'postgres'),
    password=os.getenv('DB_PASSWORD'),
    port=os.getenv('DB_PORT', '5432')
#cursor object to execute sql queries
cursor = conn.cursor()

#function that checks true or false if a table exists in the database
def table_exists_psycopg2(conn, table_name):
    # establish a cursor to execute the query
    # query checks if the table exists in the information_schema.tables
    # the query will return either true if the subqurery finds at lease one matching row and false otherwise 
    # then we return the results of the query by extratcing the row of the first column which is just the boolean result
    try:
        cur = conn.cursor()
        cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s)", (table_name,))
        return cur.fetchone()[0]
    # error handling method. If the query fails then it will print the error message and return false
    except pg.Error as e:
        print(f"Error checking table existence: {e}")
        return False
    # closes cursor object cur 
    finally:
        if cur:
            cur.close()

#uses the previous function to see if the df_orders table exists in the database
# if it does it is truncated if not then it is created with the specified columns and datatypes
if table_exists_psycopg2(conn, 'df_orders') == True:
    cursor.execute('truncate table df_orders')
elif table_exists_psycopg2(conn, 'df_orders') == False:
    cursor.execute('CREATE TABLE df_orders (order_id INT, order_date DATE, ship_mode VARCHAR(255), segment VARCHAR(255), country VARCHAR(255), city VARCHAR(255), state VARCHAR(255), postal_code INT, region VARCHAR(255), category VARCHAR(255), sub_category VARCHAR(255), product_id VARCHAR(255), quantity INT, discount FLOAT, sale_price FLOAT, profit FLOAT)')

# function that inserts every row of dataframe into an already existing table in postgresql
def execute_values(conn, df, table): 
    # first converts each row of the dataframe into a tuple by using to_numpy() and then make a list of all of the tuples 
    # this is done to make a list of each row of data 
    # this is important becasue the list is in the correct format for the execute_values function to insert the data into the table in postgresql
    tuples = [tuple(x) for x in df.to_numpy()] 
    
    # df.columns returns the column names of the dataframe which is then turned into a list 
    # "','.join" joins the list into a string connected by commas
    cols = ','.join(list(df.columns)) 
    # parameterized SQL query to execute. we will insert into the table the columns from the cols varaible
    query = "INSERT INTO %s(%s) VALUES %%s" % (table, cols) 
    # created a cursor object which is used to execute sql commands and interact with the databse 
    cursor = conn.cursor() 
    try: 
        extras.execute_values(cursor, query, tuples) 
        conn.commit() 
    # error handling method. If the query fails then it will rollback the changes made to the database and close the cursor
    # except (Exception) as error: Catches any error that occurs during the insert or commit process.
    # print("Error: %s" % error): Displays the error message to help with debugging.
    # onn.rollback(): Undoes any part of the transaction that may have executed before the error.
    # cursor.close(): Closes the cursor to clean up resources.
    # return 1: Returns an error indicator (value 1) to the calling code.
    except (Exception) as error: 
        print("Error: %s" % error) 
        conn.rollback() 
        cursor.close() 
        return 1
    # success message 
    print("the dataframe is inserted") 
    cursor.close() 

#uses the previous function to insert the dataframe into the df_orders table
execute_values(conn, df, 'df_orders')

# uses the cursor to execute a select statment on the df_orders table to check if the data has been inserted correctly
cursor.execute('SELECT * FROM df_orders')

cursor.close()
conn.close()
