from datetime import datetime
from pymongo import MongoClient
from utils import Timer

__author__ = 'nonamenix'


class LeaderBoardStatistic(object):
    """
    Calculate some statistics for leaderboards
    """
    fields = ['battles', 'vpb', 'victories', 'experience']
    max_values = {}
    rating_filter = {'battles': {'$gt': 500}}

    def __init__(self):
        db = MongoClient()['rating']
        self.leaderboard = db['leaderboard']
        self.statistics = db['statistics']
        self.points = [0.05 * i for i in range(1, 21)]

    def count(self):
        return self.leaderboard.find({}).count()

    def get_field_distribution(self, field, value, count):
        return float(self.leaderboard.find({field: {'$lt': value}}).count()) / count

    def get_max_values(self):
        max_values = {}
        for field in self.fields:
            max_values[field] = self.leaderboard.find(self.rating_filter).sort(field, -1).limit(1)[0][field]
        return max_values

    def get_stats(self):
        max_values = self.get_max_values()
        count = self.count()

        fields_points = {}
        for field in self.fields:
            fields_points[field] = [point * max_values[field] for point in self.points]

        fields_distribution = {}
        for field in self.fields:
            fields_distribution[field] = [self.get_field_distribution(field, point, count) for point in fields_points[field]]

        _stats = {
            'count': count,
            'points': fields_points,
            'distribution': fields_distribution,
            'createdAt': datetime.utcnow()
        }
        self.statistics.insert_one(_stats)
        return _stats


with Timer():
    stats = LeaderBoardStatistic()
    print stats.get_stats()





