from django.shortcuts import redirect, render
from numpy import require
from rest_framework.decorators import api_view
from rest_framework.response import Response
#from .db_extraction import DBConnection
from django.db import connections
import pandas as pd
from . import urls
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.models import User, auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password



class DBConnection:
    """
    Class for database connection
    read_table - returns a dataFrame from query
    execute_query - executes a data manipulation query
    close - used to close the connection created
    execute_count - executes the query for selection and returns count of records
    """
    def __init__(self, connection_name):
        self.conn = connections[connection_name]

    def read_table(self, query):
        """executes the query and returns df"""
        return pd.read_sql(query, self.conn)

    def execute_query(self,query):
        """executes the query for insertion or stored procedure execution"""
        cur = self.conn.cursor()
        cur.execute(query)
        cur.close()
        self.conn.commit()

    def close(self):
        """closes the connection created"""
        self.conn.close()

    def execute_count(self, query):
        """executes the query for selection and returns count of records"""
        cursor = self.conn.cursor()
        data = cursor.execute(query)
        count = cursor.fetchone()[0]
        cursor.close()
        return count


def login(request):
    # This function is called when 'login' is mentioned in url.
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = auth.authenticate(username = username, password = password)
        if user is not None:
            auth.login(request, user)

            # create role in session variables  
            tech_count = """select count(*) from technicians t join employee e 
                            on e.e_ssn = t.e_ssn where username = '{}'""".format(username)
            tc_count = """select count(*) from traffic_controllers t join employee e 
                            on e.e_ssn = t.e_ssn where username = '{}'""".format(username)
            faa_count = """select count(*) from faa_admin t join employee e 
                            on e.e_ssn = t.e_ssn where username = '{}'""".format(username)
            appdb_connection = DBConnection('default')
            tech_count = appdb_connection.execute_count(tech_count)
            tc_count = appdb_connection.execute_count(tc_count)
            faa_count = appdb_connection.execute_count(faa_count)
            if tech_count>0:
                request.session["role"] = "technician"
            elif tc_count>0:
                request.session["role"] = "traffic_controller"
            elif faa_count>0:
                request.session["role"] = "faa_admin"
            else:
                request.session["role"] = "others"

            return redirect('home')
        else:
            messages.info(request, 'Invalid credentials')
            return redirect('login')
    else:
        return render(request, 'login.html')


def logout(request):
    # This function is called when 'logout' is mentioned in url.
    auth.logout(request)
    return redirect('login')
    
@api_view(['GET'])
@login_required(login_url='/login/')
def home(request):
    # This function is called when '' is mentioned in url.
    return render(request, 'home.html')

@login_required(login_url='/login/')
@api_view(['GET'])
def user_directory(request):
    # This function is called when 'users' is mentioned in url.
    return render(request, 'user_directory.html')

@api_view(['GET'])
def get_user_details(request):
    """
    This function is called when 'getuserdetails' is mentioned in url.
    This request is made from ajax call from datatable under User directory,
    to render the dataTable and provide additional functionality like sorting, pagination
    This function handles
    - parameter extraction
    - DB connection
    - renders DataTable
    """
    
    header = ["e_name", "e_phonenumber", "e_city", "e_state", "e_country", "u_name"]

    # Extracting params from url
    try:
        
        start = request.GET['start']
        length = request.GET['length']
        search = request.GET['search[value]']
        # Below parameters are available based on sorting activity(optional)
        sort_col = request.GET.get('order[0][column]')
        sort_dir = request.GET.get('order[0][dir]')
        pass

        print("Extracted start,length,search,"
                     "sort_col,sort_dir {},{},{},{},{} using GET "
                     "request".format( start, length, search, sort_col, sort_dir))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        raise

    # Extracting data from app DB
    search = search.lower().replace("'","''")

    if sort_col is None:
        query = """SELECT e_name, e_phonenumber, e_city, e_state, e_country, u_name from personal_details_union_view
        where LOWER(e_name) like '%{}%'
        or LOWER(e_phonenumber) like '%{}%' or LOWER(e_city) like '%{}%'
        or LOWER(e_state) like '%{}%' or LOWER(e_country) like '%{}%' or LOWER(u_name) like '%{}%' 
        limit {} offset {}""".format(search, search, search, search, search, search, length, start)
    else:
        sort_col = str(int(sort_col) + 1)
        query = """SELECT e_name, e_phonenumber, e_city, e_state, e_country, u_name from personal_details_union_view
        where LOWER(e_name) like '%{}%'
        or LOWER(e_phonenumber) like '%{}%' or LOWER(e_city) like '%{}%' or LOWER(u_name) like '%{}%' 
        or LOWER(e_state) like '%{}%' or LOWER(e_country) like '%{}%' order by {} {} 
        limit {} offset {}""".format(search, search, search, search, search, search, sort_col, sort_dir, length, start)

    count_query = "SELECT COUNT(*) FROM personal_details_union_view"
    filtered_count_query = """SELECT count(*) from personal_details_union_view
                            where LOWER(e_name) like '%{}%' or LOWER(u_name) like '%{}%' 
                            or LOWER(e_phonenumber) like '%{}%' or LOWER(e_city) like '%{}%'
                            or LOWER(e_state) like '%{}%' or LOWER(e_country) like '%{}%'
                            """.format(search, search, search, search, search, search)
    try:
        # Data extraction from DB
        appdb_connection = DBConnection('default')
        app_df = appdb_connection.read_table(query)
        total_count = appdb_connection.execute_count(count_query)
        filtered_count = appdb_connection.execute_count(filtered_count_query)

        # converting column name to lower case
        app_df.columns = [column.lower() for column in app_df.columns]
        datatable_json = []

        # Preparing dataTable records
        for i in range(app_df.shape[0]):
            temp_list = []
            for column_name in header:
                temp_list.append((app_df[column_name][i]))

            datatable_json.append(temp_list)

    except Exception as e:
        print("Error occurred while extracting data from application DB."
                      "Exception type:{}, Exception value:{} occurred while extracting data from application DB.".format(
            type(e), e))
        raise
    finally:
        appdb_connection.close()

    return Response({'recordsTotal': total_count, 'recordsFiltered': filtered_count, 'data': datatable_json})


# employee management
@api_view(['GET'])
@login_required(login_url='/login/')
def admin_employee_management(request):
    # This function is called when 'employeemanagement' is mentioned in url.
    return render(request, 'employee_management.html')

@api_view(['GET'])
def get_employee_details(request):
    """
    This function is called when 'getemployeedetails' is mentioned in url.
    This request is made from ajax call from datatable under User directory,
    to render the dataTable and provide additional functionality like sorting, pagination
    This function handles
    - parameter extraction
    - DB connection
    - renders DataTable
    """
    header = ["e_ssn", "e_name", "e_phonenumber", "username", "e_street", "e_city", "e_state", "e_country", "e_pincode", "e_salary"]

    # Extracting params from url
    try:
        
        start = request.GET['start']
        length = request.GET['length']
        search = request.GET['search[value]']
        # Below parameters are available based on sorting activity(optional)
        sort_col = request.GET.get('order[0][column]')
        sort_dir = request.GET.get('order[0][dir]')
        pass

        print("Extracted start,length,search,"
                     "sort_col,sort_dir {},{},{},{},{} using GET "
                     "request".format( start, length, search, sort_col, sort_dir))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        raise

    # Extracting data from app DB
    search = search.lower().replace("'","''")

    if sort_col is None:        
        query = """SELECT e_ssn, e_name, e_phonenumber, username, e_street, e_city, e_state, e_country, e_pincode, e_salary from employee
        where LOWER(e_name) like '%{}%' or LOWER(e_ssn) like '%{}%' or LOWER(username) like '%{}%'
        or LOWER(e_phonenumber) like '%{}%' or LOWER(e_city) like '%{}%' or LOWER(e_street) like '%{}%'
        or LOWER(e_state) like '%{}%' or LOWER(e_country) like '%{}%' or LOWER(e_pincode) like '%{}%'
        or LOWER(e_salary) like '%{}%' limit {} offset {}""".format(search, search, search, search, search, search, search, search, search, search, length, start)
    else:
        sort_col = str(int(sort_col) + 1)
        query = """SELECT e_ssn, e_name, e_phonenumber, username, e_street, e_city, e_state, e_country, e_pincode, e_salary from employee
        where LOWER(e_name) like '%{}%' or LOWER(e_ssn) like '%{}%' or LOWER(username) like '%{}%'
        or LOWER(e_phonenumber) like '%{}%' or LOWER(e_city) like '%{}%' or LOWER(e_street) like '%{}%'
        or LOWER(e_state) like '%{}%' or LOWER(e_country) like '%{}%' or LOWER(e_pincode) like '%{}%'
        or LOWER(e_salary) like '%{}%' order by {} {}
        limit {} offset {}""".format(search, search, search, search, search, search, search, search, search, search, sort_col, sort_dir, length, start)

    count_query = "SELECT COUNT(*) FROM employee"
    filtered_count_query = """SELECT count(*) from employee
                            where LOWER(e_name) like '%{}%' or LOWER(e_ssn) like '%{}%' or LOWER(username) like '%{}%'
                            or LOWER(e_phonenumber) like '%{}%' or LOWER(e_city) like '%{}%' or LOWER(e_street) like '%{}%'
                            or LOWER(e_state) like '%{}%' or LOWER(e_country) like '%{}%' or LOWER(e_pincode) like '%{}%'
                            or LOWER(e_salary) like '%{}%'
                            """.format(search, search, search, search, search, search, search, search, search, search)
    #print(filtered_count_query)
    #print(count_query)
    #print(query)
    try:
        # Data extraction from DB
        appdb_connection = DBConnection('default')
        app_df = appdb_connection.read_table(query)
        total_count = appdb_connection.execute_count(count_query)
        filtered_count = appdb_connection.execute_count(filtered_count_query)

        # converting column name to lower case
        app_df.columns = [column.lower() for column in app_df.columns]
        datatable_json = []

        # Preparing dataTable records
        for i in range(app_df.shape[0]):
            temp_list = []
            for column_name in header:
                temp_list.append((app_df[column_name][i]))

            datatable_json.append(temp_list)

    except Exception as e:
        print("Error occurred while extracting data from application DB."
                      "Exception type:{}, Exception value:{} occurred while extracting data from application DB.".format(
            type(e), e))
        raise
    finally:
        appdb_connection.close()

    return Response({'recordsTotal': total_count, 'recordsFiltered': filtered_count, 'data': datatable_json})


@api_view(['POST'])
def insert_employee_details(request):
    """
    This function is called when 'insertemployeedetails' is mentioned in url.
    This request is made from ajax call from datatable under Add button,
    to add employee details
    This function handles
    - parameter extraction
    - DB connection
    - DB record creation
    """

    # Extracting params from url
    try:
        
        e_ssn = request.POST['e_ssn']
        e_name = request.POST['e_name']
        e_street = request.POST['e_street']
        e_city = request.POST['e_city']
        e_state = request.POST['e_state']
        e_country = request.POST['e_country']
        e_pincode = request.POST['e_pincode']
        model_number = request.POST['model_number']
        e_phonenumber = request.POST['e_phonenumber']
        role = request.POST['role']
        e_salary = request.POST['e_salary']
        username = request.POST['username']
        password = request.POST['password']
        e_uid = request.POST['u_id']

        print("Extracted  {},{},{},{},{},{},{},{},{},{},{},{} using GET "
                     "request".format( e_ssn, e_name, e_street, e_city, e_state, e_country, e_pincode, e_phonenumber,
                     e_salary, username, password, e_uid))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    query = """INSERT INTO employee (`e_ssn`, `e_name`, `e_street`, `e_state`, `e_city`, `e_country`, 
                                    `e_pincode`, `e_phonenumber`, `e_salary`, `username`, `password`, 
                                    `u_id`, `union_membership_number`) 
                                    VALUES ('{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}', '{}',
                                     '{}', '{}', '{}')
                                    """.format(e_ssn, e_name, e_street, e_state, e_city, e_country,
                                    e_pincode, e_phonenumber, e_salary, username, make_password(password,hasher='default'), e_uid, (e_ssn+str(e_uid)))
    
    table_name = ''                                    
    if role == "technician":
        table_name = "technicians"
    elif role == "traffic":
        table_name = "traffic_controllers"
    elif role == 'faa':
        table_name = 'faa_admin'
    
    query2 = "INSERT INTO " + table_name + "(e_ssn) VALUES('{}')".format(e_ssn)

    
    
    if role == "technician" and model_number != '' and model_number is not None:
            query3 = "INSERT INTO expertises(e_ssn, model_number) VALUES('{}', '{}')".format(e_ssn, model_number)


    print(query2)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)
        if role != "others":
            appdb_connection.execute_query(query2)
        
        if role == "technician" and model_number != '' and model_number is not None:
            appdb_connection.execute_query(query3)

        # Storing the details in Django user object for authentication purpose
        user = User.objects.create_user(username=username, password = password, first_name = e_name)
        user.save()
    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response    

    return Response({'data': 'success'})

@api_view(['POST'])
def update_employee_details(request):
    """
    This function is called when 'updateemployeedetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button,
    to update employee details
    This function handles
    - parameter extraction
    - DB connection
    - DB record update
    """

    # Extracting params from url
    try:
        
        e_ssn = request.POST['u_e_ssn']
        e_name = request.POST['u_e_name']
        e_street = request.POST['u_e_street']
        e_city = request.POST['u_e_city']
        e_state = request.POST['u_e_state']
        e_country = request.POST['u_e_country']
        e_pincode = request.POST['u_e_pincode']
        e_phonenumber = request.POST['u_e_phonenumber']
        e_salary = request.POST['u_e_salary']
        username = request.POST['u_username']
        #e_uid = request.POST['u_id']
        #union_membership_number = request.POST['union_membership_number']


        print("Extracted  {},{},{},{},{},{},{},{},{} using GET "
                     "request".format( e_ssn, e_name, e_street, e_city, e_state, e_country, e_pincode, e_phonenumber,
                     e_salary))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """UPDATE employee 
                SET `e_ssn` = '{}', `e_name` = '{}', `e_street` = '{}', `e_state` = '{}',
                `e_city` = '{}', `e_country` = '{}', `e_pincode` = '{}', `e_phonenumber` = '{}',
                `e_salary` = '{}'
                where  `e_ssn` = '{}'""".format(e_ssn, e_name, e_street, e_state, e_city, e_country,
                e_pincode, e_phonenumber, e_salary, e_ssn)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

        #Update first name in the user model as it is the only details that we are storing
        User.objects.filter(username=username).update(first_name = e_name)
        

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    return Response({'data': 'success'})


@api_view(['POST'])
def delete_employee_details(request):
    """
    This function is called when 'deleteemployeedetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button,
    to delete employee details
    This function handles
    - parameter extraction
    - DB connection
    - DB record deletion
    """

    # Extracting params from url
    try:
        
        e_ssn = request.POST['d_e_ssn']
        username = request.POST['d_username']
        print("Extracted  {}, {} using POST "
                     "request".format( e_ssn,username))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """DELETE from employee where `e_ssn` = '{}'
                """.format(e_ssn)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

        #deleting the record from User model
        User.objects.filter(username=username).delete()


    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
    
    return Response({'data': 'success'})


@api_view(['GET'])
@login_required(login_url='/login/')
def profile(request):
    # This function is called when 'profile' is mentioned in url.
    
    query = """SELECT e_ssn, e_name, e_phonenumber, username, password, e_street, e_city, e_state, e_country, e_pincode from employee
            where username = "{}" """.format(request.user.username)
    try:
        # Data extraction from DB
        appdb_connection = DBConnection('default')
        app_df = appdb_connection.read_table(query)
        context = app_df.to_dict('records')[0]
    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while extractng "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 
        return response
    finally:
        appdb_connection.close()
        print(context)
    return render(request, 'profile.html', context)


@api_view(['POST'])
def updateprofiledetails(request):
    """
    This function is called when 'updateprofiledetails' is mentioned in url.
    This request is made from ajax call from Profile page,
    to update personal details
    This function handles
    - parameter extraction
    - DB connection
    - DB record update
    """
    print("reached")

    # Extracting params from url
    try:
        
        e_ssn = request.POST['u_e_ssn']
        e_name = request.POST['u_e_name']
        e_street = request.POST['u_e_street']
        e_city = request.POST['u_e_city']
        e_state = request.POST['u_e_state']
        e_country = request.POST['u_e_country']
        e_pincode = request.POST['u_e_pincode']
        e_phonenumber = request.POST['u_e_phonenumber']
        username = request.POST['u_username']
        password = request.POST['u_password']

        print("Extracted  {},{},{},{},{},{},{},{} using GET "
                     "request".format( e_ssn, e_name, e_street, e_city, e_state, e_country, e_pincode, e_phonenumber))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """UPDATE employee 
                SET  `e_name` = '{}', `e_street` = '{}', `e_state` = '{}',
                `e_city` = '{}', `e_country` = '{}', `e_pincode` = '{}', `e_phonenumber` = '{}',
                `password` = '{}'                
                where  `e_ssn` = '{}'""".format(e_name, e_street, e_state, e_city, e_country,
                e_pincode, e_phonenumber, make_password(password,hasher='default'), e_ssn)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

        #Update first name and password in the user model as it is the only details that we are storing
        password=make_password(password,hasher='default')
        User.objects.filter(username=username).update(first_name = e_name, password = password)
        

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    return Response({'data': 'success'})


# union details
@api_view(['GET'])
@login_required(login_url='/login/')
def admin_union_management(request):
    # This function is called when 'unionmanagement' is mentioned in url.
    return render(request, 'union_management.html')

@api_view(['GET'])
def get_union_details(request):
    """
    This function is called when 'getuniondetails' is mentioned in url.
    This request is made from ajax call from datatable under User directory,
    to render the dataTable and provide additional functionality like sorting, pagination
    This function handles
    - parameter extraction
    - DB connection
    - renders DataTable
    """
    header = ["u_id", "u_name"]

    # Extracting params from url
    try:
        
        start = request.GET['start']
        length = request.GET['length']
        search = request.GET['search[value]']
        # Below parameters are available based on sorting activity(optional)
        sort_col = request.GET.get('order[0][column]')
        sort_dir = request.GET.get('order[0][dir]')
        pass

        print("Extracted start,length,search,"
                     "sort_col,sort_dir {},{},{},{},{} using GET "
                     "request".format( start, length, search, sort_col, sort_dir))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        raise

    # Extracting data from app DB
    search = search.lower().replace("'","''")

    if sort_col is None:        
        query = """SELECT u_id, u_name from `union`
        where LOWER(u_name) like '%{}%' or LOWER(u_id) like '%{}%'
        limit {} offset {}""".format(search, search, length, start)
    else:
        sort_col = str(int(sort_col) + 1)
        query = """SELECT u_id, u_name from `union`
        where LOWER(u_name) like '%{}%' or LOWER(u_id) like '%{}%'
        order by {} {}
        limit {} offset {}""".format( search, search, sort_col, sort_dir, length, start)

    count_query = "SELECT COUNT(*) FROM `union`"
    filtered_count_query = """SELECT count(*) from `union`
                            where LOWER(u_name) like '%{}%' or LOWER(u_id) like '%{}%'
                            """.format(search, search)
    #print(filtered_count_query)
    #print(count_query)
    #print(query)
    try:
        # Data extraction from DB
        appdb_connection = DBConnection('default')
        app_df = appdb_connection.read_table(query)
        total_count = appdb_connection.execute_count(count_query)
        filtered_count = appdb_connection.execute_count(filtered_count_query)

        # converting column name to lower case
        app_df.columns = [column.lower() for column in app_df.columns]
        datatable_json = []

        # Preparing dataTable records
        for i in range(app_df.shape[0]):
            temp_list = []
            for column_name in header:
                temp_list.append((app_df[column_name][i]))

            datatable_json.append(temp_list)

    except Exception as e:
        print("Error occurred while extracting data from application DB."
                      "Exception type:{}, Exception value:{} occurred while extracting data from application DB.".format(
            type(e), e))
        raise
    finally:
        appdb_connection.close()

    return Response({'recordsTotal': total_count, 'recordsFiltered': filtered_count, 'data': datatable_json})


@api_view(['POST'])
def insert_union_details(request):
    """
    This function is called when 'insertuniondetails' is mentioned in url.
    This request is made from ajax call from datatable under Add button,
    to add employee details
    This function handles
    - parameter extraction
    - DB connection
    - DB record creation
    """

    # Extracting params from url
    try:
        union_name = request.POST['union_name']
        print("Extracted  {} using GET "
                     "request".format( union_name))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    query = """INSERT INTO `union` (`u_name`) VALUES ('{}')""".format(union_name)

    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)
    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response    

    return Response({'data': 'success'})

@api_view(['POST'])
def update_union_details(request):
    """
    This function is called when 'updatuniondetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button
    This function handles
    - parameter extraction
    - DB connection
    - DB record update
    """

    # Extracting params from url
    try:
        
        u_uid = request.POST['u_uid']
        u_uname = request.POST['u_uname']


        print("Extracted  {},{} using GET "
                     "request".format( u_uid, u_uname))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """UPDATE `union` 
                SET `u_name` = '{}'
                where  `u_id` = '{}'""".format(u_uname, u_uid)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    return Response({'data': 'success'})


@api_view(['POST'])
def delete_union_details(request):
    """
    This function is called when 'deleteuniondetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button,
    to delete employee details
    This function handles
    - parameter extraction
    - DB connection
    - DB record deletion
    """

    # Extracting params from url
    try:
        d_uid = request.POST['d_uid']
        print(d_uid)
        print("Extracted  {} using POST "
                     "request".format( d_uid))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """DELETE from `union` where `u_id` = '{}'
                """.format(d_uid)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
    
    return Response({'data': 'success'})


# model management
@api_view(['GET'])
@login_required(login_url='/login/')
def admin_model_management(request):
    # This function is called when 'modelmanagement' is mentioned in url.
    return render(request, 'model_management.html')

@api_view(['GET'])
def get_model_details(request):
    """
    This function is called when 'getmodeldetails' is mentioned in url.
    This request is made from ajax call from datatable under User directory,
    to render the dataTable and provide additional functionality like sorting, pagination
    This function handles
    - parameter extraction
    - DB connection
    - renders DataTable
    """
    header = ["model_number", "m_capacity", "m_weight" ]

    # Extracting params from url
    try:
        
        start = request.GET['start']
        length = request.GET['length']
        search = request.GET['search[value]']
        # Below parameters are available based on sorting activity(optional)
        sort_col = request.GET.get('order[0][column]')
        sort_dir = request.GET.get('order[0][dir]')
        pass

        print("Extracted start,length,search,"
                     "sort_col,sort_dir {},{},{},{},{} using GET "
                     "request".format( start, length, search, sort_col, sort_dir))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        raise

    # Extracting data from app DB
    search = search.lower().replace("'","''")

    if sort_col is None:        
        query = """SELECT model_number, m_capacity, m_weight from model_details
        where LOWER(model_number) like '%{}%' or LOWER(m_capacity) like '%{}%' or LOWER(m_weight) like '%{}%'
        limit {} offset {}""".format(search, search, search, length, start)
    else:
        sort_col = str(int(sort_col) + 1)
        query = """SELECT model_number, m_capacity, m_weight from model_details
        where LOWER(model_number) like '%{}%' or LOWER(m_capacity) like '%{}%' or LOWER(m_weight) like '%{}%'
        order by {} {}
        limit {} offset {}""".format( search, search, search, sort_col, sort_dir, length, start)

    count_query = "SELECT COUNT(*) FROM model_details"
    filtered_count_query = """SELECT count(*) from model_details
                            where LOWER(model_number) like '%{}%' or LOWER(m_capacity) like '%{}%' or LOWER(m_weight) like '%{}%'
                            """.format(search, search, search)
    #print(filtered_count_query)
    #print(count_query)
    #print(query)
    try:
        # Data extraction from DB
        appdb_connection = DBConnection('default')
        app_df = appdb_connection.read_table(query)
        total_count = appdb_connection.execute_count(count_query)
        filtered_count = appdb_connection.execute_count(filtered_count_query)

        # converting column name to lower case
        app_df.columns = [column.lower() for column in app_df.columns]
        datatable_json = []

        # Preparing dataTable records
        for i in range(app_df.shape[0]):
            temp_list = []
            for column_name in header:
                temp_list.append((app_df[column_name][i]))

            datatable_json.append(temp_list)

    except Exception as e:
        print("Error occurred while extracting data from application DB."
                      "Exception type:{}, Exception value:{} occurred while extracting data from application DB.".format(
            type(e), e))
        raise
    finally:
        appdb_connection.close()

    return Response({'recordsTotal': total_count, 'recordsFiltered': filtered_count, 'data': datatable_json})


@api_view(['POST'])
def insert_model_details(request):
    """
    This function is called when 'insertmodeldetails' is mentioned in url.
    This request is made from ajax call from datatable under Add button
    This function handles
    - parameter extraction
    - DB connection
    - DB record creation
    """

    # Extracting params from url
    try:
        model_number = request.POST['model_number']
        m_capacity = request.POST['m_capacity']
        m_weight = request.POST['m_weight']
        print("Extracted  {}, {}, {} using GET "
                     "request".format(model_number, m_capacity, m_weight ))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    query = """INSERT INTO model_details (model_number, m_capacity, m_weight) 
            VALUES ('{}', '{}', '{}')""".format(model_number, m_capacity, m_weight)

    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)
    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response    

    return Response({'data': 'success'})

@api_view(['POST'])
def update_model_details(request):
    """
    This function is called when 'updatemodeldetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button
    This function handles
    - parameter extraction
    - DB connection
    - DB record update
    """

    # Extracting params from url
    try:
        
        model_number = request.POST['model_number']
        m_capacity = request.POST['m_capacity']
        m_weight = request.POST['m_weight']

        print("Extracted  {},{}, {} using GET "
                     "request".format(model_number, m_capacity, m_weight))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """UPDATE model_details 
                SET `m_capacity` = '{}', m_weight = {}
                where  `model_number` = '{}'""".format(m_capacity, m_weight, model_number)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    return Response({'data': 'success'})


@api_view(['POST'])
def delete_model_details(request):
    """
    This function is called when 'deletemodeldetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button,
    to delete employee details
    This function handles
    - parameter extraction
    - DB connection
    - DB record deletion
    """

    # Extracting params from url
    try:
        model_number = request.POST['model_number']
        
        print("Extracted  {} using POST "
                     "request".format( model_number))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """DELETE from model_details where model_number = '{}'
                """.format(model_number)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
    
    return Response({'data': 'success'})


@api_view(['POST'])
def insert_expert_details(request):
    """
    This function is called when 'insertexpertdetails' is mentioned in url.
    This request is made from ajax call from datatable under Add button
    This function handles
    - parameter extraction
    - DB connection
    - DB record creation
    """

    # Extracting params from url
    try:
        model_number = request.POST['model_number']
        e_ssn = request.POST['e_ssn']
        print("Extracted  {}, {} using GET "
                     "request".format(model_number, e_ssn))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    query = """INSERT INTO expertises (model_number, e_ssn) 
            VALUES ('{}', '{}')""".format(model_number, e_ssn)

    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)
    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response    

    return Response({'data': 'success'})



# airplane management
@api_view(['GET'])
@login_required(login_url='/login/')
def admin_airplane_management(request):
    # This function is called when 'airplanemanagement' is mentioned in url.
    return render(request, 'airplane_management.html')

@api_view(['GET'])
def get_airplane_details(request):
    """
    This function is called when 'getairplanedetails' is mentioned in url.
    This request is made from ajax call from datatable under User directory,
    to render the dataTable and provide additional functionality like sorting, pagination
    This function handles
    - parameter extraction
    - DB connection
    - renders DataTable
    """
    header = ["registration_number", "stationed_at", "airworthy", "model_number"]

    # Extracting params from url
    try:
        
        start = request.GET['start']
        length = request.GET['length']
        search = request.GET['search[value]']
        # Below parameters are available based on sorting activity(optional)
        sort_col = request.GET.get('order[0][column]')
        sort_dir = request.GET.get('order[0][dir]')
        pass

        print("Extracted start,length,search,"
                     "sort_col,sort_dir {},{},{},{},{} using GET "
                     "request".format( start, length, search, sort_col, sort_dir))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        raise

    # Extracting data from app DB
    search = search.lower().replace("'","''")

    if sort_col is None:     

        query = """SELECT registration_number, stationed_at, airworthy, model_number from airplane
        where LOWER(registration_number) like '%{}%' or LOWER(stationed_at) like '%{}%' or LOWER(airworthy) like '%{}%' or
        LOWER(model_number) like '%{}%' limit {} offset {}""".format(search, search, search, search, length, start)
    else:
        sort_col = str(int(sort_col) + 1)
        query = """SELECT registration_number, stationed_at, airworthy, model_number from airplane
        where LOWER(registration_number) like '%{}%' or LOWER(stationed_at) like '%{}%' or LOWER(airworthy) like '%{}%' or
        LOWER(model_number) like '%{}%'
        order by {} {}
        limit {} offset {}""".format( search, search, search, search, sort_col, sort_dir, length, start)

    count_query = "SELECT COUNT(*) FROM airplane"
    filtered_count_query = """SELECT count(*) from airplane
                            where LOWER(registration_number) like '%{}%' or LOWER(stationed_at) like '%{}%' or LOWER(airworthy) like '%{}%' or
                            LOWER(model_number) like '%{}%'
                            """.format(search, search, search, search)
    #print(filtered_count_query)
    #print(count_query)
    #print(query)
    try:
        # Data extraction from DB
        appdb_connection = DBConnection('default')
        app_df = appdb_connection.read_table(query)
        app_df = app_df.fillna('')

        total_count = appdb_connection.execute_count(count_query)
        filtered_count = appdb_connection.execute_count(filtered_count_query)

        # converting column name to lower case
        app_df.columns = [column.lower() for column in app_df.columns]
        datatable_json = []

        # Preparing dataTable records
        for i in range(app_df.shape[0]):
            temp_list = []
            for column_name in header:
                temp_list.append((app_df[column_name][i]))

            datatable_json.append(temp_list)

    except Exception as e:
        print("Error occurred while extracting data from application DB."
                      "Exception type:{}, Exception value:{} occurred while extracting data from application DB.".format(
            type(e), e))
        raise
    finally:
        appdb_connection.close()

    return Response({'recordsTotal': total_count, 'recordsFiltered': filtered_count, 'data': datatable_json})


@api_view(['POST'])
def insert_airplane_details(request):
    """
    This function is called when 'insertairplanedetails' is mentioned in url.
    This request is made from ajax call from datatable under Add button
    This function handles
    - parameter extraction
    - DB connection
    - DB record creation
    """

    # Extracting params from url
    try:
        registration_number = request.POST['registration_number']
        airworthy = request.POST['airworthy']
        stationed_at = request.POST['stationed_at']
        model_number = request.POST['model_number']
        
        print("Extracted  {}, {}, {}, {} using GET "
                     "request".format(registration_number, airworthy, stationed_at,model_number ))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
    if stationed_at == '':
        stationed_at = 'NULL'
    if airworthy == '':
        airworthy = 'NULL'
    query = """INSERT INTO airplane (registration_number, stationed_at, airworthy, model_number) 
            VALUES ('{}', {}, {}, '{}')""".format(registration_number, stationed_at, airworthy, model_number)

    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)
    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response    

    return Response({'data': 'success'})

@api_view(['POST'])
def update_airplane_details(request):
    """
    This function is called when 'updateairplanedetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button
    This function handles
    - parameter extraction
    - DB connection
    - DB record update
    """

    # Extracting params from url
    try:
        
        
        registration_number = request.POST['registration_number']
        airworthy = request.POST['airworthy']
        stationed_at = request.POST['stationed_at']
        model_number = request.POST['model_number']

        if stationed_at == '':
            stationed_at = 'NULL'
        if airworthy == '':
            airworthy = 'NULL'

        print("Extracted  {},{}, {}, {} using GET "
                     "request".format(model_number, registration_number, airworthy, stationed_at))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """UPDATE airplane 
                SET `model_number` = '{}', airworthy = {}, stationed_at = {}
                where  `registration_number` = '{}'""".format(model_number, airworthy, stationed_at, registration_number)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    return Response({'data': 'success'})


@api_view(['POST'])
def delete_airplane_details(request):
    """
    This function is called when 'deleteairplanedetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button,
    to delete employee details
    This function handles
    - parameter extraction
    - DB connection
    - DB record deletion
    """

    # Extracting params from url
    try:
        registration_number = request.POST['registration_number']
        
        print("Extracted  {} using POST "
                     "request".format( registration_number))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """DELETE from airplane where registration_number = '{}'
                """.format(registration_number)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
    
    return Response({'data': 'success'})


# drop_down values
@api_view(['GET', 'POST'])
def dropdown(request):
    
    # Extracting params from url
    try:
        
        param = request.GET['param']
        print("Extracted  {} using GET request".format(param))

    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    if param == 'model':
        query = """select distinct model_number from model_details"""
    elif param == 'union':
        query = """select distinct u_id, u_name from `union`"""
    elif param == 'employee':
        # technicians
        query = """select distinct e.e_ssn, e_name from employee e join technicians t on t.e_ssn = e.e_ssn"""
        

    # Object creation of DBConnection class
    appdb_connection = DBConnection('default')
    try:
        values = appdb_connection.read_table(query)
    except Exception as e:
        print("Error occurred while extracting data from application DB."
                      "Exception type:{}, Exception value:{} occurred while extracting data from "
                      "application DB.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
    finally:
        appdb_connection.close()

    drop_down_item = []
    if param == 'model':
        for index, row in values.iterrows():
            drop_down_item .append({'id': row['model_number'],
                                        'text': row["model_number"]})
    elif param == 'union':
        for index, row in values.iterrows():
            drop_down_item .append({'id': row['u_id'],
                                        'text': row["u_name"]})
    
    elif param == 'employee':
        for index, row in values.iterrows():
            drop_down_item .append({'id': row['e_ssn'],
                                        'text': row["e_name"]})

    """
    To filter based on search term
    """
    if request.GET.get('q'):
        q = request.GET['q']
        drop_down_item = list(filter(lambda drop_down_element: q in drop_down_element['text'], drop_down_item))

    return Response({'results': drop_down_item})



# traffic controllers

def station_management(request):
    # This function is called when 'airplanemanagement' is mentioned in url.
    return render(request, 'station_management.html')

@api_view(['GET'])
def get_station_details(request):
    """
    This request is made from ajax call from datatable,
    to render the dataTable and provide additional functionality like sorting, pagination
    This function handles
    - parameter extraction
    - DB connection
    - renders DataTable
    """
    header = ["registration_number", "stationed_at"]

    # Extracting params from url
    try:
        
        start = request.GET['start']
        length = request.GET['length']
        search = request.GET['search[value]']
        # Below parameters are available based on sorting activity(optional)
        sort_col = request.GET.get('order[0][column]')
        sort_dir = request.GET.get('order[0][dir]')
        pass

        print("Extracted start,length,search,"
                     "sort_col,sort_dir {},{},{},{},{} using GET "
                     "request".format( start, length, search, sort_col, sort_dir))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        raise

    # Extracting data from app DB
    search = search.lower().replace("'","''")

    if sort_col is None:     

        query = """SELECT registration_number, stationed_at from airplane
        where LOWER(registration_number) like '%{}%' or LOWER(stationed_at) like '%{}%' 
        limit {} offset {}""".format(search, search, length, start)
    else:
        sort_col = str(int(sort_col) + 1)
        query = """SELECT registration_number, stationed_at from airplane
        where LOWER(registration_number) like '%{}%' or LOWER(stationed_at) like '%{}%' order by {} {}
        limit {} offset {}""".format( search, search, sort_col, sort_dir, length, start)

    count_query = "SELECT COUNT(*) FROM airplane"
    filtered_count_query = """SELECT count(*) from airplane
                            where LOWER(registration_number) like '%{}%' or LOWER(stationed_at) like '%{}%' 
                            """.format(search, search)
    #print(filtered_count_query)
    #print(count_query)
    #print(query)
    try:
        # Data extraction from DB
        appdb_connection = DBConnection('default')
        app_df = appdb_connection.read_table(query)
        app_df = app_df.fillna('')

        total_count = appdb_connection.execute_count(count_query)
        filtered_count = appdb_connection.execute_count(filtered_count_query)

        # converting column name to lower case
        app_df.columns = [column.lower() for column in app_df.columns]
        datatable_json = []

        # Preparing dataTable records
        for i in range(app_df.shape[0]):
            temp_list = []
            for column_name in header:
                temp_list.append((app_df[column_name][i]))

            datatable_json.append(temp_list)

    except Exception as e:
        print("Error occurred while extracting data from application DB."
                      "Exception type:{}, Exception value:{} occurred while extracting data from application DB.".format(
            type(e), e))
        raise
    finally:
        appdb_connection.close()

    return Response({'recordsTotal': total_count, 'recordsFiltered': filtered_count, 'data': datatable_json})

@api_view(['POST'])
def update_station_details(request):
    """
    This function is called when 'updateairplanedetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button
    This function handles
    - parameter extraction
    - DB connection
    - DB record update
    """

    # Extracting params from url
    try:
        
        
        registration_number = request.POST['registration_number']
        stationed_at = request.POST['stationed_at']

        if stationed_at == '':
            stationed_at = 'NULL'

        print("Extracted  {}, {} using GET "
                     "request".format(registration_number, stationed_at))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """UPDATE airplane 
                SET  stationed_at = {}
                where  `registration_number` = '{}'""".format( stationed_at, registration_number)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    return Response({'data': 'success'})

# faa admin
def airworthy_management(request):
    # This function is called when 'airplanemanagement' is mentioned in url.
    return render(request, 'airworthy_management.html')

@api_view(['GET'])
def get_airworthy_details(request):
    """
    This function is called when 'getairplanedetails' is mentioned in url.
    This request is made from ajax call from datatable under User directory,
    to render the dataTable and provide additional functionality like sorting, pagination
    This function handles
    - parameter extraction
    - DB connection
    - renders DataTable
    """
    header = ["registration_number", "airworthy"]

    # Extracting params from url
    try:
        
        start = request.GET['start']
        length = request.GET['length']
        search = request.GET['search[value]']
        # Below parameters are available based on sorting activity(optional)
        sort_col = request.GET.get('order[0][column]')
        sort_dir = request.GET.get('order[0][dir]')
        pass

        print("Extracted start,length,search,"
                     "sort_col,sort_dir {},{},{},{},{} using GET "
                     "request".format( start, length, search, sort_col, sort_dir))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        raise

    # Extracting data from app DB
    search = search.lower().replace("'","''")

    if sort_col is None:     

        query = """SELECT registration_number, airworthy,from airplane
        where LOWER(registration_number) like '%{}%'  or LOWER(airworthy) like '%{}%' or
        limit {} offset {}""".format(search, search, length, start)
    else:
        sort_col = str(int(sort_col) + 1)
        query = """SELECT registration_number, airworthy from airplane
        where LOWER(registration_number) like '%{}%' or LOWER(airworthy) like '%{}%' 
        order by {} {}
        limit {} offset {}""".format( search, search, sort_col, sort_dir, length, start)

    count_query = "SELECT COUNT(*) FROM airplane"
    filtered_count_query = """SELECT count(*) from airplane
                            where LOWER(registration_number) like '%{}%' or LOWER(airworthy) like '%{}%' 
                            """.format(search, search)
    #print(filtered_count_query)
    #print(count_query)
    #print(query)
    try:
        # Data extraction from DB
        appdb_connection = DBConnection('default')
        app_df = appdb_connection.read_table(query)
        app_df = app_df.fillna('')

        total_count = appdb_connection.execute_count(count_query)
        filtered_count = appdb_connection.execute_count(filtered_count_query)

        # converting column name to lower case
        app_df.columns = [column.lower() for column in app_df.columns]
        datatable_json = []

        # Preparing dataTable records
        for i in range(app_df.shape[0]):
            temp_list = []
            for column_name in header:
                temp_list.append((app_df[column_name][i]))

            datatable_json.append(temp_list)

    except Exception as e:
        print("Error occurred while extracting data from application DB."
                      "Exception type:{}, Exception value:{} occurred while extracting data from application DB.".format(
            type(e), e))
        raise
    finally:
        appdb_connection.close()

    return Response({'recordsTotal': total_count, 'recordsFiltered': filtered_count, 'data': datatable_json})


@api_view(['POST'])
def update_airworthy_details(request):
    """
    This function is called when 'updateairplanedetails' is mentioned in url.
    This request is made from ajax call from datatable under Edit button
    This function handles
    - parameter extraction
    - DB connection
    - DB record update
    """

    # Extracting params from url
    try:
        
        
        registration_number = request.POST['registration_number']
        airworthy = request.POST['airworthy']
        
        if airworthy == '':
            airworthy = 'NULL'

        print("Extracted {}, {} using GET "
                     "request".format( registration_number, airworthy))
    except Exception as e:
        print("Error occurred while parameter extraction."
                "Exception type:{}, Exception value:{} occurred while parameter "
                "extraction.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response

    query = """UPDATE airplane 
                SET  airworthy = {}
                where  `registration_number` = '{}'""".format(airworthy, registration_number)
                                    
    print(query)
    try:
        appdb_connection = DBConnection('default')
        appdb_connection.execute_query(query)

    except Exception as e:
        print("Error occurred while saving data."
                "Exception type:{}, Exception value:{} while saving "
                "data.".format(type(e), e))
        response = Response({"error": str(e)})
        response.status_code = 500 # To announce that the user isn't allowed to publish
        return response
        
    return Response({'data': 'success'})

