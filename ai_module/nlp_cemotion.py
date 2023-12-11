
def get_sentiment(c,text):
    try:
        return c.predict(text)
    except BaseException as e:
                print("请稍后")
                print(e)



