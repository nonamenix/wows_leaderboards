Meteor.publish("rating", function (page, sortField, realm, username) {
    var page_size = 20;
    var filter = {battles: {$gt: 500}};

    if (realm != 'all' && realm !== undefined) {
        filter.realm = realm;
    }

    if (username !== null) {
        filter.user = {$regex: username + ".*", $options: 'i'};
    }

    var extra = {
        sort: {},
        limit: page_size,
        skip: page * page_size
    };
    extra['sort'][sortField] = -1;
    return BasicRatings.find(filter, extra);
});

Meteor.publish('ratingSize', function () {
    Counts.publish(this, 'ratingSize', BasicRatings.find());
});
