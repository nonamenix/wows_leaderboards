Meteor.publish("rating", function (page) {
    var page_size = 20;
    return BasicRatings.find({battles: {$gt: 500}}, {
        sort: {'vpb': -1},
        limit: page_size,
        skip: page * page_size
    });
});

Meteor.publish('ratingSize', function () {
    Counts.publish(this, 'ratingSize', BasicRatings.find());
});

