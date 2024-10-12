
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Profile, Course, Quiz, Question, StudentAnswer, Enrollment
from django.contrib.auth.models import User
from .forms import RegistrationForm, CourseForm, QuizForm, QuestionForm
from django.forms import modelformset_factory





def home(request):
    return render(request, 'home.html')



def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type')

        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            try:
                profile = Profile.objects.get(user=user)
            except Profile.DoesNotExist:
                messages.error(request, 'User profile not found.')
                return render(request, 'login.html')

            if profile.user_type == user_type:
                login(request, user)
                if user_type == 'teacher':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('student_dashboard')
            else:
                messages.error(request, 'Invalid user type selected.')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'login.html')


def user_logout(request):
    logout(request)
    return redirect('home')



def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()
            profile = Profile.objects.get(user=user)
            profile.user_type = 'student'
            profile.save()
            messages.success(request, 'Registration successful. You can now login.')
            return redirect('login')
    else:
        form = RegistrationForm()
    return render(request, 'register.html', {'form': form})



@login_required
def teacher_dashboard(request):
    if request.user.profile.user_type != 'teacher':
        messages.error(request, 'Access denied.')
        return redirect('home')
    courses = Course.objects.filter(teacher=request.user)
    return render(request, 'teacher_dashboard.html', {'courses': courses})


@login_required
def student_dashboard(request):
    if request.user.profile.user_type != 'student':
        messages.error(request, 'Access denied.')
        return redirect('home')

    enrollments = Enrollment.objects.filter(student=request.user)
    quizzes = Quiz.objects.filter(course__in=[enrollment.course for enrollment in enrollments])

    enrolled_course_ids = enrollments.values_list('course_id', flat=True)
    available_courses = Course.objects.exclude(id__in=enrolled_course_ids)

    return render(request, 'student_dashboard.html', {
        'enrollments': enrollments,
        'quizzes': quizzes,
        'available_courses': available_courses,
    })

@login_required
def create_course(request):
    if request.user.profile.user_type != 'teacher':
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.teacher = request.user
            course.save()
            messages.success(request, 'Course created successfully.')
            return redirect('teacher_dashboard')
    else:
        form = CourseForm()
    return render(request, 'create_course.html', {'form': form})



@login_required
def add_quiz(request):
    if request.user.profile.user_type != 'teacher':
        messages.error(request, 'Access denied.')
        return redirect('home')
    if request.method == 'POST':
        quiz_form = QuizForm(request.POST)
        if quiz_form.is_valid():
            quiz = quiz_form.save(commit=False)
            quiz.save()
            return redirect('add_questions', quiz.id)
    else:
        form = QuizForm()
    return render(request, 'add_quiz.html', {'form': form})



@login_required
def view_quizzes(request, course_id):
    if request.user.profile.user_type != 'teacher':
        messages.error(request, 'Access denied.')
        return redirect('home')
    course = get_object_or_404(Course, id=course_id, teacher=request.user)
    quizzes = Quiz.objects.filter(course=course)
    return render(request, 'view_quizzes.html', {'quizzes': quizzes, 'course': course})



@login_required
def start_quiz(request, course_id):
    if request.user.profile.user_type != 'student':
        messages.error(request, 'Access denied.')
        return redirect('home')
    course = get_object_or_404(Course, id=course_id)
    enrollment = Enrollment.objects.filter(course=course, student=request.user).first()
    if not enrollment:
        messages.error(request, 'You are not enrolled in this course.')
        return redirect('student_dashboard')
    quiz = Quiz.objects.filter(course=course).first()
    if not quiz:
        messages.error(request, 'No quiz available for this course.')
        return redirect('student_dashboard')
    questions = quiz.questions.all()
    if request.method == 'POST':
        for question in questions:
            selected_option = request.POST.get(f'question_{question.id}')
            if selected_option:
                StudentAnswer.objects.create(
                    student=request.user,
                    question=question,
                    selected_option=selected_option
                )
    
        correct = 0
        for answer in StudentAnswer.objects.filter(student=request.user, question__quiz=quiz):
            if answer.selected_option == answer.question.correct_option:
                correct += 1
        score = correct
        total = questions.count()
        return render(request, 'quiz_result.html', {'score': score, 'total': total, 'quiz': quiz})
    return render(request, 'start_quiz.html', {'quiz': quiz, 'questions': questions})


@login_required
def quiz_result(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id)
    answers = StudentAnswer.objects.filter(student=request.user, question__quiz=quiz)
    correct = 0
    for answer in answers:
        if answer.selected_option == answer.question.correct_option:
            correct += 1
    total = quiz.questions.count()
    score = correct
    return render(request, 'quiz_result.html', {'score': score, 'total': total, 'quiz': quiz})


@login_required
def add_questions(request, quiz_id):
    if request.user.profile.user_type != 'teacher':
        messages.error(request, 'Access denied.')
        return redirect('home')
    
    quiz = get_object_or_404(Quiz, id=quiz_id, course__teacher=request.user)
    QuestionFormSet = modelformset_factory(
        Question,
        form=QuestionForm,
        extra=10,
        max_num=10,
        can_delete=False
    )
    
    if request.method == 'POST':
        formset = QuestionFormSet(request.POST, queryset=Question.objects.none())
        if formset.is_valid():
            for form in formset:
                question = form.save(commit=False)
                question.quiz = quiz
                question.save()
            messages.success(request, 'Questions added successfully.')
            return redirect('view_quizzes', quiz.course.id)
    else:
        formset = QuestionFormSet(queryset=Question.objects.none())
    
    return render(request, 'add_questions.html', {'formset': formset, 'quiz': quiz})

@login_required
def course_list(request):
    courses = Course.objects.all()  # Get all courses
    return render(request, 'course_list.html', {'courses': courses})

@login_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.method == 'POST':
        
        Enrollment.objects.create(student=request.user, course=course)
        messages.success(request, f'You have successfully enrolled in {course.title}.')
        return redirect('course_list')  
    return render(request, 'enroll_course.html', {'course': course})
