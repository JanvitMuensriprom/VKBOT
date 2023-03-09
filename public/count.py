import vk_api
from datetime import datetime, timedelta

# Setting up the VK session with an access token
access_token = '2a3d72c72a3d72c72a3d72c7b1292f81eb22a3d2a3d72c74e38a51a1737368d2c80af10'
vk_session = vk_api.VkApi(token=access_token)

# Getting the wall posts
vk = vk_session.get_api()
wall = vk.wall.get(owner_id='786189749', count=100)

# Filtering the posts to only include those from today
today = datetime.today().strftime('%Y-%m-%d')
today_posts = [post for post in wall['items'] if datetime.fromtimestamp(post['date']).strftime('%Y-%m-%d') == today]

# Printing the number of the latest post
print("Number of the latest post: ", wall['count'])

print("Number of posts from today: ", len(today_posts))