from flask_restx import Resource, fields, Namespace
from src.models.user import UserModel, RoleModel, ReviewModel
from src.schemas.user import UserSchema, RoleSchema, ReviewSchema
from flask import request, jsonify
from src.server.extensions import bcrypt


user_ns = Namespace(name='users', description='Users operations')

# ------- Users -------
user_schema = UserSchema()
user_list_schema = UserSchema(many=True)

user_model = user_ns.model('User', {
    'name': fields.String(required=True, max_length=50, description='User name.'),
    'email': fields.String(required=True, max_length=50, description='User email.'),
    'password': fields.String(required=True, max_length=50, description='User password no hashed.'),
    'active': fields.Boolean(default=True, description='User state account.'),
    'role_name': fields.String(required=True, description='User role name.')
})

USER_NOT_FOUND = 'User not found.'

# ------- Roles -------
role_schema = RoleSchema()
role_list_schema = RoleSchema(many=True)

role_model = user_ns.model('Role', {
    'name': fields.String(required=True, max_length=20, description='Role name.'),
    'description': fields.String(required=True, max_length=255, description='Role description.')
})

ROLE_NOT_FOUND = 'Role not found.'

# ------- Reviews -------
review_schema = ReviewSchema()
review_list_schema = ReviewSchema(many=True)

review_model = user_ns.model('Review', {
    'title': fields.String(required=True, max_length=50, description='Review title.'),
    'body': fields.String(required=True, max_length=2000, description='Review body.'),
    'artwork': fields.String(required=True, description='Type of artwork analyzed in the review.'),
    'gender': fields.String(required=True, description='Genre of artwork review.'),
    'is_public': fields.Boolean(required=True, description='Review privacy.'),
    'user_id': fields.Integer(required=True, description='User id (review author).')
})

allowed_artwork_types = ['Film', 'Book']
allowed_gender_types = ['Horror', 'Thriller', 'Comedy',
                        'Romantic comedy', 'Action ', 'Romance',
                        'Science fiction', 'Classic movie', 'Western',
                        'Drama', 'Animation', 'Foreign', 'War', 'Adventure', 'Musical']

REVIEW_ARTWORK_NOT_FOUND = 'Review artwork not found.'
REVIEW_GENDER_NOT_FOUND = 'Review gender not found.'
REVIEW_NOT_FOUND = 'Review not found.'


@user_ns.route('/<int:user_id>')
class User(Resource):
    @user_ns.response(200, 'Get an user.')
    def get(self, user_id):
        user_data = UserModel.find_by_id(user_id)
        if user_data:
            return user_schema.dump(user_data), 200
        return {'message': USER_NOT_FOUND}, 404

    @user_ns.expect(user_model)
    @user_ns.response(200, 'Update an user.')
    def put(self, user_id):
        user_json = request.get_json()
        user_data = UserModel.find_by_id(user_id)
        if user_data:
            user_data.name = user_json['name']
            user_data.name = user_json['email']
            user_data.name = user_json['password_hash']
            user_data.active = user_json['active']
            user_data.role_name = user_json['role_name']

            user_data.save_to_db()
            return user_schema.dump(user_data), 200
        return {'message': USER_NOT_FOUND}, 404

    @user_ns.response(204, 'Delete an user.')
    def delete(self, user_id):
        user_data = UserModel.find_by_id(user_id)
        if user_data:
            user_data.delete_from_db()
            return '', 204
        return {'message': USER_NOT_FOUND}, 404


@user_ns.route('/')
class UserList(Resource):
    @user_ns.response(200, 'Get all the users.')
    def get(self):
        return user_list_schema.dump(UserModel.find_all()), 200

    @user_ns.expect(user_model)
    @user_ns.response(201, 'Create an user.')
    def post(self):
        user_json = request.get_json()

        # o client não precisa enviar um password criptografado, pelo fato de utilizar um servidor https(SSL) e o request tambem criptografar
        password = user_json['password']
        password_hash = bcrypt.generate_password_hash(password)
        del user_json['password']
        user_json['password_hash'] = password_hash

        role_name = user_json['role_name']
        role_data = RoleModel.find_by_name(role_name)

        if role_data:
            user_data = user_schema.load(user_json)
            user_data.save_to_db()

            return user_schema.dump(user_data), 201
        else:
            return {'message': ROLE_NOT_FOUND}, 404


@user_ns.route('/roles/<role_name>')
class Role(Resource):
    @user_ns.response(200, 'Get an user role.')
    def get(self, role_name):
        role_data = RoleModel.find_by_name(role_name)
        if role_data:
            return role_schema.dump(role_data), 200
        return {'message': ROLE_NOT_FOUND}, 404

    @user_ns.expect(role_model)
    @user_ns.response(200, 'Update an user role.')
    def put(self, role_name):
        role_json = request.get_json()
        role_data = RoleModel.find_by_name(role_name)
        if role_data:
            role_data.name = role_json['name']
            role_data.description = role_json['description']
            role_data.save_to_db()
            return role_schema.dump(role_data), 200
        return {'message': ROLE_NOT_FOUND}, 404

    @user_ns.response(204, 'Delete an user role.')
    def delete(self, role_name):
        role_data = RoleModel.find_by_name(role_name)
        if role_data:
            role_data.delete_from_db()
            return '', 204
        return {'message': ROLE_NOT_FOUND}, 404


@user_ns.route('/roles')
class RoleList(Resource):
    @user_ns.response(200, 'Get all the users roles.')
    def get(self):
        return role_list_schema.dump(RoleModel.find_all()), 200

    @user_ns.expect(role_model)
    @user_ns.response(201, 'Create an user role.')
    def post(self):
        role_json = request.get_json()

        role_data = role_schema.load(role_json)
        role_data.save_to_db()

        return role_schema.dump(role_data), 201


@user_ns.route('/reviews/<int:review_id>')
class Review(Resource):
    @user_ns.response(200, 'Get an review.')
    def get(self, review_id):
        review_data = ReviewModel.find_by_id(review_id)
        if review_data:
            return review_schema.dump(review_data), 200
        return {'message': REVIEW_NOT_FOUND}, 404

    @user_ns.expect(review_model)
    @user_ns.response(200, 'Update an review.')
    def put(self, review_id):
        review_json = request.get_json()
        review_data = ReviewModel.find_by_id(review_id)
        if review_data:
            if review_json['artwork'] not in allowed_artwork_types:
                return {'message': REVIEW_ARTWORK_NOT_FOUND}, 404
            if review_json['gender'] not in allowed_gender_types:
                return {'message': REVIEW_GENDER_NOT_FOUND}, 404
            review_data.title = review_json['title']
            review_data.body = review_json['body']
            review_data.artwork = review_json['artwork']
            review_data.gender = review_json['gender']
            review_data.is_public = review_json['is_public']

            review_data.save_to_db()
            return review_schema.dump(review_data), 200
        return {'message': REVIEW_NOT_FOUND}, 404

    @user_ns.response(204, 'Delete an review.')
    def delete(self, review_id):
        review_data = ReviewModel.find_by_id(review_id)
        if review_data:
            review_data.delete_from_db()
            return '', 204
        return {'message': REVIEW_NOT_FOUND}, 404


@user_ns.route('/reviews')
class ReviewList(Resource):
    @user_ns.response(200, 'Get all reviews.')
    def get(self):
        return review_list_schema.dump(ReviewModel.find_all()), 200

    @user_ns.expect(review_model)
    @user_ns.response(201, 'Create an review.')
    def post(self):
        review_json = request.get_json()

        user_id = review_json['user_id']
        user_data = UserModel.find_by_id(user_id)

        if user_data:
            if review_json['artwork'] not in allowed_artwork_types:
                return {'message': REVIEW_ARTWORK_NOT_FOUND}, 404
            if review_json['gender'] not in allowed_gender_types:
                return {'message': REVIEW_GENDER_NOT_FOUND}, 404

            review_data = review_schema.load(review_json)
            review_data.save_to_db()
            return review_schema.dump(review_data), 201
        else:
            return {'message': USER_NOT_FOUND}, 404
