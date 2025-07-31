#!/bin/bash

# PRMAgent Graph Database Test Script
# This script tests various relationship types and fact patterns
# to validate how the graph database stores and connects information

echo "Starting PRMAgent Graph Database Tests..."
echo "========================================="

# Test 1: Basic friend and location information
echo "Test 1: Adding friends with locations..."
python PRMAgent.py "Add my college friend Sarah who lives in Portland and works as a software engineer at Nike"

# Test 2: Family relationships
echo "Test 2: Adding family members..."
python PRMAgent.py "My sister Emily is married to David, they live in Austin and have three kids: Maya age 8, Lucas age 6, and baby Zoe"

# Test 3: Professional connections
echo "Test 3: Adding work connections..."
python PRMAgent.py "My colleague Marcus from the marketing department graduated from Stanford and plays guitar in a jazz band on weekends"

# Test 4: Complex multi-person relationships
echo "Test 4: Adding group relationships..."
python PRMAgent.py "Sarah introduced me to her roommate Alex who is studying medicine at OHSU, and Alex's boyfriend Jake who owns a coffee shop downtown"

# Test 5: Updating existing relationships
echo "Test 5: Adding details to existing people..."
python PRMAgent.py "Emily just got promoted to senior manager at Dell and is planning to move to a bigger house in Cedar Park"

# Test 6: Hobby and interest connections
echo "Test 6: Adding hobby-based relationships..."
python PRMAgent.py "I met Chen and Roberto at the rock climbing gym - Chen is a teacher and Roberto works in finance, they both love bouldering"

# Test 7: Long-distance relationships
echo "Test 7: Adding international connections..."
python PRMAgent.py "My friend Yuki moved back to Tokyo after college, she's working at a tech startup and recently got engaged to her boyfriend Hiroshi who is an architect"

# Test 8: Multiple shared interests
echo "Test 8: Adding people with multiple connections..."
python PRMAgent.py "Tom from my neighborhood is actually Marcus's brother-in-law, and he also knows Sarah from their CrossFit gym"

# Test 9: Professional and personal overlap
echo "Test 9: Adding mixed professional/personal relationships..."
python PRMAgent.py "Dr. Jennifer Martinez is both my dentist and Emily's yoga instructor, she has two rescue dogs named Pepper and Sage"

# Test 10: Educational connections
echo "Test 10: Adding school connections..."
python PRMAgent.py "My high school friend Michael is now a lawyer in Chicago, married to Lisa who teaches elementary school, they have twin boys in Little League"

# Test 11: Multi-generational relationships
echo "Test 11: Adding family across generations..."
python PRMAgent.py "My grandmother Rose lives in Florida with my step-grandfather Frank, who has two adult children from his first marriage: Patricia and Robert"

# Test 12: Business partnerships
echo "Test 12: Adding business relationships..."
python PRMAgent.py "Jake's coffee shop partners with local baker Maria Gonzalez, who supplies pastries and is married to contractor Luis who renovated Emily's kitchen"

# Test 13: Event-based connections
echo "Test 13: Adding event connections..."
python PRMAgent.py "At Sarah's birthday party I met her coworkers: designer Sophie, data analyst Kevin, and project manager Priya who just returned from maternity leave"

# Test 14: Nested relationship updates
echo "Test 14: Updating nested relationships..."
python PRMAgent.py "Chen's teaching partner is Amanda, who is married to fire captain Rodriguez, and they volunteer together at the animal shelter with Dr. Martinez"

# Test 15: Geographic clustering
echo "Test 15: Adding location-based clusters..."
python PRMAgent.py "In my Austin network: Emily and David are neighbors with retired couple Bob and Linda, who babysit Maya and Lucas sometimes"

# Test 16: Professional hierarchy
echo "Test 16: Adding workplace hierarchy..."
python PRMAgent.py "Marcus reports to VP Janet Williams, who is friends with Nike executive Susan Chen - Sarah's boss and Kevin's former manager"

# Test 17: Relationship status changes
echo "Test 17: Updating relationship statuses..."
python PRMAgent.py "Michael and Lisa are getting divorced, Michael is dating his law school classmate Rachel who lives in Milwaukee"

# Test 18: Complex family blending
echo "Test 18: Adding blended family relationships..."
python PRMAgent.py "Patricia has two kids from her marriage to Tony: teenager Jason and 12-year-old Emma, who are close with their step-cousins Maya and Lucas"

# Test 19: Professional skill connections
echo "Test 19: Adding skill-based networks..."
python PRMAgent.py "Roberto teaches rock climbing to beginners including nurse practitioner Diana, architect student Ben, and retired teacher Margaret"

# Test 20: Social media connections
echo "Test 20: Adding online-to-offline relationships..."
python PRMAgent.py "Through Instagram I connected with photographer Anna who shot Sophie's wedding, Anna's partner Jamie is a chef who knows Maria the baker"

# Test 21: Travel connections
echo "Test 21: Adding travel-based relationships..."
python PRMAgent.py "During my trip to Tokyo, Yuki introduced me to her friends: designer Kenji, English teacher Sakura, and businessman Takeshi who collects vintage cameras"

# Test 22: Multi-relationship validation
echo "Test 22: Testing multiple relationship types..."
python PRMAgent.py "Hiroshi's architecture firm designed the building where Jake's coffee shop is located, and Hiroshi plays tennis with Roberto on weekends"

# Test 23: Interest group expansion
echo "Test 23: Adding interest group members..."
python PRMAgent.py "The jazz band Marcus plays in includes drummer Patricia (Frank's daughter), bassist Miguel, and singer Zara who teaches at Chen's school"

# Test 24: Final complex network test
echo "Test 24: Adding final network connections..."
python PRMAgent.py "Amanda volunteers at the same animal shelter as Dr. Martinez and Luis, where they met foster coordinator Beth who is Sophie's sister"

# Test 25: Relationship validation and closure
echo "Test 25: Final relationship confirmation..."
python PRMAgent.py "Confirm that Rose and Frank are planning to visit Emily's family in Austin, and Jake is catering their anniversary party with Maria's pastries"

echo "========================================="
echo "PRMAgent Graph Database Tests Complete!"
echo "Total test calls executed: 25"
echo "Check your graph database for relationship mappings and network growth patterns."