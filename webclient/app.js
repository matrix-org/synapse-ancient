var synapseClient = angular.module('synapseClient', [
    'ngRoute',
    'LoginController',
    'ChatController'
]);

synapseClient.config(['$routeProvider',
    function($routeProvider) {
        $routeProvider.
            when('/login', {
                templateUrl: 'login/login.html',
                controller: 'LoginController'
            }).
            when('/chat', {
                templateUrl: 'chat/chat.html',
                controller: 'ChatController'
            }).
            otherwise({
                redirectTo: '/login'
            });
    }]);


synapseClient
    .factory('state', function () {
        'use strict';
        var state = {};
        return {
            "state": state,
        };
    })
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
        }
    }]);