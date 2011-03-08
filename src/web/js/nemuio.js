jQuery.noConflict();
jQuery(document).ready(function($){
	
	mainLoop();
	
	var timerId = setInterval(mainLoop, 1500);
	var errorCount = 0;
	
	$(window).click(function(){
		mainLoop();
	});
	
	function mainLoop() {
		var maxRand;
		
		if($(window).width() > 1900){
			maxRand = 15;
		}else if($(window).width() > 1200){
			maxRand = 6;
		}else{
			maxRand = 4;
		}
		
		var rand = Math.floor( Math.random() * maxRand);
		var i;

		for(i=0;i<rand;i++){
			addTweet();
		}
	}
	
	function addTweet() {
		if(errorCount > 200) return;
		$.getJSON('/api/get_tweet', function(data) {
			if(data){
				var height = $(window).height();
				var width = $(window).width();
				
				var time = Math.floor( Math.random() * 10 * 1000 + 5000);
				var $box = null;
				var $baloon = null;
				
				var className;
				var baloonWidth;
				var baloonHeight;
				
				if(data.text.length < 10){
					className = 'baloon1';
					baloonWidth = 230;
					baloonHeight = 100;
				} else if(data.text.length < 40){
					className = 'baloon2';
					baloonWidth = 300;
					baloonHeight = 150;
				} else if(data.text.length < 70){
					className = 'baloon3';
					baloonWidth = 430;
					baloonHeight = 190;
				} else {
					className = 'baloon3';
					baloonWidth = 430;
					baloonHeight = 190;
				}
				
				var top = Math.floor( Math.random() * (height - baloonHeight));
				var left = Math.floor( Math.random() * (width - baloonWidth));
				
				var baloonImage = 'baloon' + Math.floor( Math.random() * 3) + '.png';
				$baloon = $('<div/>').addClass(className);
				$baloon.append($('<img/>').attr('src','/images/' + baloonImage).width(baloonWidth).height(baloonHeight));
				
				$box = $('<div/>').addClass('tweet');
				$box.append($('<img/>').attr('src', data.profile_image_url).attr('width', 30));
				
				var $tweet = null;
				$tweet = $('<div/>').addClass('tweetBody');
				$tweet.append($('<a/>').text(data.name).attr('href', 'http://twitter.com/' + data.screen_name).addClass('name'));
				$tweet.append($('<p/>').text(data.text).addClass('text'));
				if(data.delta != '-'){
					$tweet.append($('<p/>').text(data.delta + '秒まえ').addClass('delta'));
				}
				
				$box.append($tweet);
				$baloon.append($box);
				
				$baloon.css('display', 'block');
				$baloon.css('left', left);
				$baloon.css('top', top);
				$baloon.fadeIn('slow').delay(time).fadeOut('slow', function() { $(this).remove(); });
				
				$('body').append($baloon);
 			}
		}).success(function() { errorCount = 0; }).error(function() { errorCount++; });
	}
});