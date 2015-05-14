Session.setDefault('ratingPage', 0)


Meteor.autorun(function () {
    Meteor.subscribe('rating', Session.get('ratingPage'));
    Meteor.subscribe('ratingSize');
});


Template.leaderboard.helpers({
    ratings: function () {
        return BasicRatings.find({});
    }
});

Template.rating.helpers({
    prettyRealm: function(realm){
        realms = {
            ru: 'Russia',
            eu: 'Europe',
            com: 'America',
            asia: 'Asia'
        };
        return realms[realm]
    }
    ,
    prettyPercent: function (victories_percent) {
        return  (victories_percent).toPrecision(4);
    }
});
Template.leaderboard.events({
    'click #next-page': function (evnt, tmpl) {
        Session.set('ratingPage', Session.get('ratingPage') + 1);

    },
    'click #prev-page': function (evnt, tmpl) {
        var currentPage = Session.get('ratingPage');
        if (currentPage > 0) {
            Session.set('ratingPage', Session.get('ratingPage') - 1);
        }
    }
})
