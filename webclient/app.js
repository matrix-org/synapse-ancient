var synapseClient = angular.module('synapseClient', [
    'ngRoute',
    'LoginController',
    'RoomController',
    'RoomsController',
    'matrixService'
]);

synapseClient.config(['$routeProvider',
    function($routeProvider) {
        $routeProvider.
            when('/login', {
                templateUrl: 'login/login.html',
                controller: 'LoginController'
            }).
            when('/room/:room_id', {
                templateUrl: 'room/room.html',
                controller: 'RoomController'
            }).
            when('/rooms', {
                templateUrl: 'rooms/rooms.html',
                controller: 'RoomsController'
            }).
            otherwise({
                redirectTo: '/login'
            });
    }]);

synapseClient.run(['$location', 'matrixService' , function($location, matrixService) {
    // If we have no persistent login information, go to the login page
    var config = matrixService.config();
    if (!config || !config.access_token) {
        $location.path("login");
    }
}]);

synapseClient
    .directive('ngEnter', function () {
        return function (scope, element, attrs) {
            element.bind("keydown keypress", function (event) {
                if(event.which === 13) {
                    scope.$apply(function () {
                        scope.$eval(attrs.ngEnter);
                    });
                    event.preventDefault();
                }
            });
        };
    })
    .directive('autoFocus', ['$timeout', function($timeout) {
        return {
            link: function(scope, element, attr) {
                $timeout(function() { element[0].focus() }, 0);
            }
        };
    }]);


// @TODO: We need a class utility
synapseClient.computeUserId = function(user_name, homeserver_name) {
    return "@" + user_name + ":" + homeserver_name;
};