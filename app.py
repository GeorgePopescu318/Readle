from flask import Flask, redirect, render_template, request, make_response, session, jsonify, url_for,send_from_directory
import secrets
from functools import wraps
import firebase_admin
from firebase_admin import credentials, firestore, auth
from datetime import timedelta
import os
from dotenv import load_dotenv
import firebase_query as qr
import openAiPrompt as qz
from firebase_admin.firestore import SERVER_TIMESTAMP
from datetime import datetime, timedelta, timezone
import re
from uuid import uuid4

from flask import send_file
load_dotenv()



app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'static/images')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
# Configure Flask-Uploads for images

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Configure session cookie settings
app.config['SESSION_COOKIE_SECURE'] = True  # Ensure cookies are sent over HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True  # Prevent JavaScript access to cookies
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)  # Adjust session expiration as needed
app.config['SESSION_REFRESH_EACH_REQUEST'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Can be 'Strict', 'Lax', or 'None'


# Firebase Admin SDK setup
cred = credentials.Certificate("firebase-auth.json")
firebase_admin.initialize_app(cred)
db = firestore.client()



# def add_quiz_to_db():
#     quiz = qz.generate_quiz()
#     qr.insert_document(db, "Book/yVnYd1GEh2TlSXlE03Ee/Quiz", quiz)
    
# add_quiz_to_db()
    

########################################D
""" Authentication and Authorization """
# data = {
#     "question1": "Who is the main protagonist of 'Baltagul'?",
#     "1answer1": "Gheorghiță",
#     "1answer2": "Vitoria Lipan (Correct)",
#     "1answer3": "Nechifor Lipan",

#     "question2": "What is the driving force behind Vitoria Lipan's journey in 'Baltagul'?",
#     "2answer1": "To find her missing husband (Correct)",
#     "2answer2": "To sell cattle at a fair",
#     "2answer3": "To visit her daughter in another village",

#     "question3": "Who accompanies Vitoria Lipan in her search for her husband?",
#     "3answer1": "Her daughter Minodora",
#     "3answer2": "Her son Gheorghiță (Correct)",
#     "3answer3": "Her brother-in-law Ilie",

#     "question4": "What evidence does Vitoria find that confirms her husband was murdered in 'Baltagul'?",
#     "4answer1": "A confession letter",
#     "4answer2": "Witness testimony",
#     "4answer3": "His hatchet and a bloody stone (Correct)",

#     "question5": "What is the setting of the novel 'Baltagul'?",
#     "5answer1": "The Moldovan Carpathians (Correct)",
#     "5answer2": "The Danube Plains",
#     "5answer3": "The city of Bucharest"
# }
# qr.insert_into_array(db,"User/VsIylI7O9Ew7v9rofgM8/Note","g9ZkdSEbdLtB36Rjzdw0","Notes",data)
# qr.insert_document(db,"User/VsIylI7O9Ew7v9rofgM8/Note","")
# result = qr.get_documents_with_status(db,"User/VsIylI7O9Ew7v9rofgM8/Note","Book_Name","==","real1")
# if result == []:
#     print("nu")
# print(result)
# qr.insert_document(db,"Book/DEVkViGknQTB4hqtUxHB/Quiz",data)
# print(qr.get_document(db,'User','VsIylI7O9Ew7v9rofgM8'))
# Decorator for routes that require authentication
def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_role= qr.get_document(db, 'User', session['user']['user_id'])["Role"]
        if  user_role != "admin" :
            return redirect(url_for('not_logged'))
        return f(*args, **kwargs)
    return decorated_function
# session['user']
@app.route('/auth', methods=['POST'])
def authorize():
    # Temporary delay to work around the "Token used too early" error.
    
    token = request.headers.get('Authorization')
    if not token or not token.startswith('Bearer '):
        return jsonify({"error": "Unauthorized"}), 401

    # Remove "Bearer " from token string
    token = token[7:]
    data = request.get_json() or {}
    display_name_from_js = data.get('displayName', '')
    
    try:
        # Verify the token using Firebase Admin SDK
        decoded_token = auth.verify_id_token(token)
        uid = decoded_token.get('uid')
        email = decoded_token.get('email')

        # Reference to the Firestore "User" collection using uid as document ID
        user_ref = db.collection('User').document(uid)
        user_doc = user_ref.get()

        if not user_doc.exists:
            # New user: create a document in Firestore
            user_data = {
                "Role":"user",
                "Titles": ["Reader"],
                "Main_title": "Reader",
                "Favourites": [],
                "Email": email,
                "Made_quizzes": 0,
                "Name": display_name_from_js,
                "last_failed_attempt": "1970-01-01T00:00:00.000000",
                "Quizzes_taken":{},
                "Points":0,
                "Covers":["Default.jpg"],
                "Main_cover":"Default.jpg",
                "CreatedAt": firestore.SERVER_TIMESTAMP
            }
            user_ref.set(user_data)
            print(f"Created new user in Firestore: {uid}")
        else:
            print(f"User {uid} already exists in Firestore.")

        session['user'] = decoded_token
        print("Session user:", session['user'])
        # Instead of a redirect, return a JSON response.
        return jsonify({"success": True, "redirect": url_for('home')})
    except Exception as e:
        print("Error during token verification:", e)
        return jsonify({"error": "Unauthorized"}), 401

#####################
""" Public Routes """

@app.route('/')
def home():
    books = qr.get_all_docs(db,"Book")
    role = 'user'
    if 'user' in session:
        user_id = session['user']['user_id']
        user_doc = qr.get_document(db, 'User', user_id)
        role = user_doc.get('Role', [])
    if books:
        return render_template('home.html',books=books,role=role)
    else:
        return "error home page", 404

# @app.route('/book/<book_id>')
# def book_page(book_id):
#     book_data = qr.get_document(db, 'Book', book_id)
#     reward_message = request.args.get('reward_message', '') 

#     if book_data:
#         return render_template('book.html', book=book_data, bookId=book_id, reward_message=reward_message)
#     else:
#         return "Error loading Book", 404

@app.route('/book/<book_id>/add_favorite', methods=['POST'])
def add_fav(book_id):
    if 'user' in session:
        user_id = session['user']['user_id']
        user_path = f'User/{user_id}'
        user_doc = qr.get_document(db, 'User', user_id)
        favourites = user_doc.get('Favourites', [])
        if book_id not in favourites:
            qr.insert_into_array(db, "User", user_id, 'Favourites', book_id)
            return jsonify({"success": True, "message": "Book added to favorites!"})
        return jsonify({"success": False, "message": "Book is already in favorites."})
    else:
        return render_template('not_logged.html')


@app.route('/book/<book_id>/submit_review', methods=['POST'])
def submit_review(book_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    try:
        data = request.get_json()
        user_id = session['user']['user_id']
        user_ref = db.collection('User').document(user_id)
        user = user_ref.get().to_dict()

        review_data = {
            'user_id': user_id,
            'user_name': user.get('Name', 'Anonymous'),
            'rating': data['rating'],
            'text': data['text'],
            'timestamp': SERVER_TIMESTAMP
        }

        # Add review to book's reviews subcollection
        review_ref = db.collection(f'Book/{book_id}/Reviews').document()
        review_ref.set(review_data)

        return jsonify({"success": True, "message": "Review submitted successfully"})
    
    except Exception as e:
        print(f"Error submitting review: {str(e)}")
        return jsonify({"success": False, "message": "Error submitting review"}), 500

# Update the book_page route
@app.route('/book/<book_id>')
def book_page(book_id):
    book_data = qr.get_document(db, 'Book', book_id)
    reviews_ref = db.collection(f'Book/{book_id}/Reviews').stream()
    
    reviews = []
    for doc in reviews_ref:
        review_data = doc.to_dict()
        review_data['id'] = doc.id  # Adaugă ID-ul documentului în datele recenziei
        reviews.append(review_data)
    
    # Calculează rating-ul mediu
    total_ratings = sum(review.get('rating', 0) for review in reviews)
    num_reviews = len(reviews)
    average_rating = total_ratings / num_reviews if num_reviews > 0 else 0

    if book_data:
        return render_template('book.html', 
                             book=book_data, 
                             bookId=book_id, 
                             reviews=reviews,
                             average_rating=average_rating,
                             num_reviews=num_reviews)
    else:
        return "Error loading Book", 404   
@app.route('/book/<book_id>/delete_review/<review_id>', methods=['DELETE'])
def delete_review(book_id, review_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    user_id = session['user']['user_id']
    review_ref = db.collection(f'Book/{book_id}/Reviews').document(review_id)
    review = review_ref.get()

    if not review.exists:
        return jsonify({"success": False, "message": "Review not found"}), 404

    if review.to_dict().get('user_id') != user_id:
        return jsonify({"success": False, "message": "Unauthorized"}), 403

    try:
        review_ref.delete()
        return jsonify({"success": True, "message": "Review deleted successfully"})
    except Exception as e:
        print(f"Error deleting review: {str(e)}")
        return jsonify({"success": False, "message": "Error deleting review"}), 500

@app.route('/user/<user_id>')
def user_profile(user_id):
    try:
        user_data = qr.get_document(db, 'User', user_id)
        if not user_data:
            return jsonify({"success": False, "message": "Book not found in favorites."}), 404
            
        return render_template('profile.html', user=user_data)
    except Exception as e:
        print(f"Error fetching user profile: {str(e)}")
        return jsonify({"success": False, "message": "Book not found in favorites."}), 404

@app.route('/mylist/delete/<book_id>', methods=['DELETE'])
def delete_favorite(book_id):
    if 'user' in session:
        user_id = session['user']['user_id']
        user_path = f'User/{user_id}'
        
        try:
            user = qr.get_document(db, 'User', user_id)
            favorites = user.get('Favourites', [])
            
            if book_id not in favorites:
                return jsonify({"success": False, "message": "Book not found in favorites."}), 404

            qr.delete_array_element(db, "User", user_id, "Favourites", book_id)
            return jsonify({"success": True, "message": "Book removed from favorites!"})

        except Exception as e:
            return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500
    else:
        render_template('not_logged.html')



# @app.route('/book/<book_id>/quiz', methods=['GET', 'POST'])
@app.route('/book/<book_id>/quiz', methods=['GET', 'POST'])
def quiz(book_id):
    if 'user' in session:
        user_id = session['user']['user_id']  # You might want to dynamically get the logged-in user
        user_data = qr.get_document(db, 'User', user_id)
        
        if user_data and 'last_failed_attempt' in user_data:
            last_failed_time = datetime.fromisoformat(user_data['last_failed_attempt'])
        
        # Ensure it is timezone-aware
            if last_failed_time.tzinfo is None:
                last_failed_time = last_failed_time.replace(tzinfo=timezone.utc)

        datetime_now = datetime.now(timezone.utc)

        if datetime_now - last_failed_time < timedelta(minutes=1):
            return "You must wait 2 minutes before retrying the quiz.", 403  # Forbidden response

        book = qr.get_document(db, 'Book', book_id)
        path = f"Book/{book_id}/Quiz"
        quizzes = qr.get_all_docs(db, path)

        if not quizzes:
            return "Error loading Quiz", 404

        processed_quizzes = []
        correct_answers = {}

        for quiz in quizzes:
            for key, value in quiz.items():
                if key.startswith('question'):
                    question_number = key.replace('question', '')
                    options = []

                    for opt_idx in range(1, 4):
                        option_key = f'{question_number}answer{opt_idx}'
                        option = quiz.get(option_key)
                        if option:
                            options.append(option)
                            if "(correct)" in option:
                                correct_answers[f'q{question_number}'] = option 

                    processed_quizzes.append({
                        'question': value,
                        'options': options
                    })
        
        if request.method == 'POST':
            user_answers = request.form.to_dict()
            score = sum(
                1 for q, correct in correct_answers.items() if user_answers.get(q) == correct
            )


            if score >= 3 and score < 5:
                correct_made_quiz = user_data.get('Made_quizzes', 0) + 1
                qr.update_existing_document(db, 'User', user_id, 'Made_quizzes', correct_made_quiz)
                
                failed_timestamp = datetime.utcnow().isoformat()
                qr.update_existing_document(db, 'User', user_id, 'last_failed_attempt', failed_timestamp)

                reward_message = f"You scored {score}/5 and earned a reward. You can try again for the perfect score tomorrow."
                return render_template('book.html', book=book, bookId=book_id, reward_message=reward_message)
            
            elif score == 5:
                correct_made_quiz = user_data.get('Made_quizzes', 0) + 1
                qr.update_existing_document(db, 'User', user_id, 'Made_quizzes', correct_made_quiz)

                reward_message = f"Congratulations! You just got a perfect score and were rewarded the title of 'Pula Mea'."
                return render_template('quiz.html', book=book, quiz=quizzes, score=score, reward_message=reward_message, bookId=book_id)

            
            elif score < 3:
                failed_timestamp = datetime.utcnow().isoformat()
                qr.update_existing_document(db, 'User', user_id, 'last_failed_attempt', failed_timestamp)

                reward_message = f"You only scored {score}/5, not enough to pass the quiz. Try again in 2 minutes!"
                return render_template('book.html', book=book, bookId=book_id, reward_message=reward_message)
    else:
        return render_template('not_logged.html')



# print(session)

@app.route('/mylist')
def mylist():
    if 'user' in session:
        user_list = qr.get_document(db, 'User', session['user']['user_id'])['Favourites']
        book_list = []
        # session['user']
        for id in user_list:
            elem = [qr.get_document(db, 'Book', id), id]
            book_list.append(elem)
            
        if book_list:
            return render_template('mylist.html', books = book_list)
        else:
            return render_template('mylist.html', books = [])
    return render_template('not_logged.html')

@app.route('/login')
def login():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    else:
        return render_template('login.html')

@app.route('/signup')
def signup():
    print("da")
    if 'user' in session:
        return redirect(url_for('dashboard'))
    else:
        return render_template('signup.html')

@app.route('/profile')
def profile():
    if 'user' in session:
        user_id = session['user']['user_id']
        user_data = qr.get_document(db, 'User', user_id)
        return render_template('profile.html', user=user_data)
    else:
        return render_template('not_logged.html')



# Adaugă după ruta /profile
@app.route('/shop')
def shop():
    if 'user' in session:
        user_id = session['user']['user_id']
        user_data = qr.get_document(db, 'User', user_id)
        shop_items = qr.get_all_docs(db, 'Shop')
        return render_template('shop.html', user=user_data, shop_items=shop_items)
    return render_template('not_logged.html')

@app.route('/purchase_cover/<cover_id>', methods=['POST'])
def purchase_cover(cover_id):
    if 'user' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    user_id = session['user']['user_id']
    user_ref = db.collection('User').document(user_id)
    user_data = user_ref.get().to_dict()
    cover_data = qr.get_document(db, 'Shop', cover_id)

    if not cover_data:
        return jsonify({"success": False, "message": "Cover not found"}), 404

    if cover_data['Image_path'] in user_data.get('Covers', []):
        return jsonify({"success": False, "message": "You already own this cover"}), 400

    if user_data.get('Points', 0) < cover_data['Price']:
        return jsonify({"success": False, "message": "Insufficient points"}), 400

    try:
        # Update user points and purchased covers
        user_ref.update({
            'Points': firestore.Increment(-cover_data['Price']),
            'Covers': firestore.ArrayUnion([cover_data['Image_path']])
        })
        return jsonify({"success": True, "message": "Cover purchased successfully"})
    except Exception as e:
        print(f"Error purchasing cover: {str(e)}")
        return jsonify({"success": False, "message": "Error purchasing cover"}), 500

@app.route('/equip_cover', methods=['POST'])
def equip_cover():
    if 'user' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    user_id = session['user']['user_id']
    cover_path = request.json.get('Main_cover')
    user_ref = db.collection('User').document(user_id)
    
    try:
        user_ref.update({
            'Main_cover': cover_path
        })
        return jsonify({"success": True, "message": "Cover equipped successfully"})
    except Exception as e:
        print(f"Error equipping cover: {str(e)}")
        return jsonify({"success": False, "message": "Error equipping cover"}), 500
        
@app.route('/update_main_title', methods=['POST'])
def update_main_title():
    if 'user' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401
    
    try:
        data = request.get_json()
        new_title = data.get('new_title')
        user_id = session['user']['user_id']
        
        # Update Firestore
        user_ref = db.collection('User').document(user_id)
        user_ref.update({
            'Main_title': new_title
        })
        
        # Update the session if needed
        if 'user' in session:
            session['user']['Main_title'] = new_title
        
        return jsonify({"success": True, "message": "Title updated successfully"})
    
    except Exception as e:
        print(f"Error updating title: {str(e)}")
        return jsonify({"success": False, "message": "Error updating title"}), 500


@app.route('/reset-password')
def reset_password():
        return render_template('forgot_password.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/logout')
@auth_required
def logout():
    session.pop('user', None)  # Remove the user from session
    response = make_response(redirect(url_for('login')))
    response.set_cookie('session', '', expires=0)  # Optionally clear the session cookie
    return response

@app.route('/notes', methods=['GET'])
def notes():
    if 'user' in session:
        # user = qr.get_documents_with_status(db, 'User', 'Name', '==', session['user']['name'])
        user_id = session['user']['user_id']
        notes = qr.get_all_docs(db, f'User/{user_id}/Note')
        return render_template('notes.html', notes=notes)
    else:
        return render_template("not_logged.html")
    if 'user' in session:
        user = qr.get_documents_with_status(db, 'User', 'Name', '==', session['user']['name'])
        user_id = user[0][1]
        notes = qr.get_all_docs(db, f'User/{user_id}/Note')
        return render_template('notes.html', notes=notes)
    else:
        return render_template("not_logged.html")

#aici

# CRUD Routes for Notes
@app.route('/notes/add', methods=['POST'])
def add_note():
    if 'user' in session:
        data = request.json
        user = qr.get_documents_with_status(db, 'User', 'Name', '==', session['user']['name'])
        user_id = user[0][1]
        note_ref = f'User/{user_id}/Note'

        new_note = {
            "Book_Name": data.get('Book_Name'),
            "Notes": [
                {
                    "Page_nr": int(data.get('Page_nr')),
                    "Text": data.get('Text')
                }
            ]
        }
        result = qr.get_documents_with_status(db,"User/" + session['user']['user_id'] + "/Note","Book_Name","==",new_note["Book_Name"])
        # print(result[0][1])
        if(result == []):
            qr.insert_document(db, note_ref, new_note)
        else:
            qr.insert_into_array(db, note_ref, result[0][1], "Notes", new_note["Notes"][0])
        return jsonify({"success": True, "message": "Notă adăugată cu succes"}), 201
    else:
        return render_template("not_logged.html")


@app.route('/notes/update/<note_id>', methods=['PUT'])
def update_note(note_id):
    if 'user' in session:
        # Parse JSON request body
        data = request.json

        # Get the old and new note data
        old_note = {
            "Page_nr": int(data.get('old_Page_nr')),
            "Text": data.get('old_Text')
        }
        print(old_note)
        new_note = {
            "Page_nr": int(data.get('new_Page_nr')),
            "Text": data.get('new_Text')
        }
        print(new_note)
        # Fetch the user
        user = qr.get_documents_with_status(db, 'User', 'Name', '==', session['user']['name'])
        user_id = user[0][1]

        # Define the note reference
        collection_name = f'User/{user_id}/Note'
        document_id = note_id

        # Delete the old note
        qr.delete_array_element(db, collection_name, document_id, "Notes", old_note)

        # Add the new note
        qr.insert_into_array(db, collection_name, document_id, "Notes", new_note)

        return jsonify({"success": True, "message": "Notă actualizată cu succes"})
    else:
        return render_template("not_logged.html")


@app.route('/notes/delete/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    if 'user' in session:
        user = qr.get_documents_with_status(db, 'User', 'Name', '==', session['user']['name'])
        user_id = user[0][1]
        collection_name = f'User/{user_id}/Note'
        document_id = note_id

        # Preluăm datele trimise de la frontend
        data = request.json
        print(data)
        page_nr = data.get('Page_nr')
        text = data.get('Text')

        # Validare date primite
        if not page_nr or not text:
            return jsonify({"success": False, "message": "Date invalide trimise"}), 400

        # Construcția datelor pentru ștergere
        note_to_remove = {
            "Page_nr": int(page_nr),  # Convertim la int pentru potrivirea exactă
            "Text": text
        }

        # Șterge nota specifică din array-ul Notes
        try:
            qr.delete_array_element(db, collection_name, document_id, "Notes", note_to_remove)
        except Exception as e:
            return jsonify({"success": False, "message": f"Eroare la ștergerea notei: {str(e)}"}), 500

        result = qr.get_document(db, collection_name, document_id)

        if(result["Notes"] == []):
            qr.delete_document(db, collection_name, document_id)

        return jsonify({"success": True, "message": "Notă ștearsă cu succes"})
    else:
        return render_template("not_logged.html")


@app.route('/notes/view/<note_id>', methods=['GET'])
def view_note(note_id):
    if 'user' in session:
        user = qr.get_documents_with_status(db, 'User', 'Name', '==', session['user']['name'])
        user_id = user[0][1]
        note_ref = f'User/{user_id}/Note'

    note = qr.get_document(db, note_ref, note_id)
    return jsonify(note)
#aici


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sanitize_filename(filename):
    cleaned = re.sub(r'[^a-zA-Z0-9_\-.]', '_', filename)
    return f"{uuid4().hex[:8]}_{cleaned}"

##############################################
""" Private Routes (Require authorization) """

@admin
@app.route('/book/add', methods=['GET'])
def add_book_form():
    return render_template('add_page.html') 

@admin
@app.route('/add_page', methods=['GET'])
def add_page(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@admin
@app.route('/book/add_book', methods=['POST'])
def add_book():
    file = request.files.get('Image')
    filename = None

    if file and file.filename != '':
        if not allowed_file(file.filename):
            return jsonify({"success": False, "message": "Invalid file type"}), 400
        
        filename = sanitize_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    new_book = {
        "Name": request.form.get('Name'),
        "Author": request.form.get('Author'),
        "Genre": request.form.get('Genre'),
        "Title": request.form.get('Title'),
        "Image": filename
    }

    # Your database logic here
    result = qr.get_documents_with_status(db, "Book", "Name", "==", new_book["Name"])

    if not result:
        qr.insert_document(db, 'Book', new_book)
    else:
        book_id = result[0][1]
        # updates = {k: v for k, v in updates.items() if v is not None}
        # if updates:
        if new_book["Author"]:
            qr.update_existing_document(db, 'Book', book_id, "Author",new_book['Author'])
        if new_book["Genre"]:
            qr.update_existing_document(db, 'Book', book_id, "Genre",new_book['Genre'])
        if new_book["Title"]:
            qr.update_existing_document(db, 'Book', book_id, "Title",new_book['Title'])
        if new_book["Image"]:
            qr.update_existing_document(db, 'Book', book_id, "Image",new_book['Image'])

    # Redirect to the home page after adding the book
    return redirect(url_for('home'))  # Replace 'home' with the name of your home route

@admin
@app.route('/book/delete/<book_id>', methods=['POST'])
def delete_book(book_id):
    # Get the book document from database
    book_doc = qr.get_document(db, 'Book', book_id)
    
    if not book_doc:
        return jsonify({"success": False, "message": "Invalid file type"}), 400

    # Delete associated image file if it exists
    if book_doc.get('Image'):
        try:
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], book_doc['Image'])
            if os.path.exists(image_path):
                os.remove(image_path)
        except Exception as e:
            app.logger.error(f"Error deleting image file: {str(e)}")

    # Delete the book document from database
    qr.delete_document(db, 'Book', book_id)

    return redirect(url_for('home'))

@app.route('/dashboard')
@auth_required
def dashboard():

    return render_template('dashboard.html')

# data = {
#     "Author": "Ioan Slavici",
#     "Genre": "Drama",
#     "Image": "\\rand1",
#     "Name": "Mara"
# }
# qr.insert_document(db,'Book',data)
# books = qr.get_all_docs(db,'Book')
# print(books[0])
# mara = qr.get_documents_with_status(db,'Book','Name','==','Mara')
# # qr.delete_document(db,"Book",mara[0][1])
# # print(mara)
# id = mara[0][1]
# qr.update_existing_document(db,'Book',id,"Name","Mara")
# print(id)
# print(mara)

if __name__ == '__main__':
    app.run(debug=True)