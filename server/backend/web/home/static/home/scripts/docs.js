$('.navbar-page .nav-link').removeClass('active');
$('.navbar-page .nav-link.docs-link').addClass('active');

$('.structure-folder .name-folder').click(function () {
    let is_ul_element = $(this).parent().next().is("ul");
    if (is_ul_element == true) { // caso o próximo elemento seja uma "ul"
        $(this).parent().next().toggle(); // toogle na ul
        $(this).find('img').toggleClass('rotate-arrow');
    }
});