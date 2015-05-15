Meteor.publish("rating", function (page, sortField, realm) {
    var page_size = 20;
    var filter = {};
    if (realm != 'all' && realm !== undefined) {
        filter.realm = realm;
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
