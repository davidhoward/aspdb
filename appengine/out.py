from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
import xml.etree.ElementTree

class Handler(webapp.RequestHandler):
    def get(self):
        self.post()
    def post(self):
        print self.request.url
        root = xml.etree.ElementTree.Element(self.request.url)
        rtree = xml.etree.ElementTree.ElementTree(root)
        rtree.write(self.response.out)


application = webapp.WSGIApplication( [('/.*', Handler)])

def main():
    run_wsgi_app(application)

if __name__ == '__main__':
    main()

