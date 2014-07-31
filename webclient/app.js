var synapseClient = angular.module('synapseClient', [
    'ngRoute',
    'LoginController',
    'RoomController',
    'RoomsController'
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

synapseClient.run(['$location', function($location) {
    // If we have no persistent login information, go to the login page
    var config = synapseClient.getConfig();
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


/* 
 * Permanent storage of user information
 * The config contains:
 *    - homeserver_name
 *    - homeserver_url
 *    - access_token
 *    - user_name
 *    - user_id
 *    - version: the version of this cache
 *    
 * @TODO: This is out of the Angular concepts. Need to find how to implement it
 *  with angular objects
 */
synapseClient.configVersion = 0;
synapseClient.getConfig = function() {
    var config = localStorage.getItem("config");
    if (config) {
        config = JSON.parse(config);

        // Reset the cache if the version loaded is not the expected one
        if (synapseClient.configVersion !== config.version) {
            config = undefined;
        }
    }
    return config;
};

synapseClient.setConfig = function(config) {
    config.version = synapseClient.configVersion;
    localStorage.setItem("config", JSON.stringify(config));
};
