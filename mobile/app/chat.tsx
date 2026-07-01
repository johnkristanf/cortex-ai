import React, { useState, useRef, useEffect } from 'react';
import { StyleSheet, View, Text, TextInput, TouchableOpacity, FlatList, KeyboardAvoidingView, Platform } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { LinearGradient } from 'expo-linear-gradient';
import Markdown from 'react-native-markdown-display';
import { chatApi } from '../src/api/chat';
import { useLocalSearchParams } from 'expo-router';
import { supabase } from '../src/lib/supabase';

interface Message {
  id: string;
  text: string;
  isUser: boolean;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    { id: '1', text: 'Hello! I am Cortex Ai. How can I help you today?', isUser: false }
  ]);
  const [inputText, setInputText] = useState('');
  const flatListRef = useRef<FlatList>(null);
  const { google_token } = useLocalSearchParams<{ google_token?: string }>();

  useEffect(() => {
    if (!google_token) return;

    const subscribeToDrive = async () => {
      try {
        const { data: { user } } = await supabase.auth.getUser();
        if (!user) return;

        const folder_id = "14Dq8gmScifYG2G9t-ct5JFMxd3xZjdR4"

        await chatApi.subscribeToDrive(
          user.id,
          folder_id, // Hardcoded for now, replace with actual
          google_token,
          'default'
        );
      } catch (error) {
        console.error('Failed to subscribe to Drive:', error);
      }
    };

    subscribeToDrive();
  }, [google_token]);

  const sendMessage = async () => {
    if (!inputText.trim()) return;

    const userText = inputText.trim();
    const newUserMessage: Message = {
      id: Date.now().toString(),
      text: userText,
      isUser: true,
    };

    setMessages(prev => [...prev, newUserMessage]);
    setInputText('');

    try {
      // Create an empty bot message immediately
      const botMessageId = Date.now().toString() + '-bot';
      const initialBotMessage: Message = {
        id: botMessageId,
        text: '',
        isUser: false,
      };
      setMessages(prev => [...prev, initialBotMessage]);

      await chatApi.sendMessage(
        userText, 
        'default', 
        google_token ?? null,
        (textChunk) => {
          setMessages(prev => 
            prev.map(msg => 
              msg.id === botMessageId 
                ? { ...msg, text: msg.text + textChunk }
                : msg
            )
          );
        }
      );
    } catch (error) {
      const errorMessage: Message = {
        id: Date.now().toString(),
        text: 'Error connecting to the assistant. Please try again.',
        isUser: false,
      };
      setMessages(prev => [...prev, errorMessage]);
    }
  };

  const renderMessage = ({ item }: { item: Message }) => {
    const isUser = item.isUser;
    return (
      <View style={[styles.messageBubble, isUser ? styles.userBubble : styles.botBubble]}>
        {!isUser && (
          <View style={styles.botAvatar}>
            <Ionicons name="hardware-chip" size={16} color="#FFFFFF" />
          </View>
        )}
        <View style={[styles.messageContent, isUser ? styles.userMessageContent : styles.botMessageContent]}>
          {isUser ? (
            <Text style={[styles.messageText, styles.userMessageText]}>
              {item.text}
            </Text>
          ) : (
            <Markdown style={markdownStyles}>
              {item.text}
            </Markdown>
          )}
        </View>
      </View>
    );
  };

  return (
    <SafeAreaView style={styles.container} edges={['top', 'left', 'right']}>
      <View style={styles.header}>
        <View style={styles.headerTitleContainer}>
          <Ionicons name="hardware-chip-outline" size={24} color="#3B82F6" />
          <Text style={styles.headerTitle}>Cortex Ai</Text>
        </View>
        <TouchableOpacity style={styles.headerButton}>
          <Ionicons name="settings-outline" size={24} color="#64748B" />
        </TouchableOpacity>
      </View>

      <KeyboardAvoidingView 
        style={styles.keyboardAvoid} 
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >
        <FlatList
          ref={flatListRef}
          data={messages}
          keyExtractor={item => item.id}
          renderItem={renderMessage}
          contentContainerStyle={styles.messageList}
          onContentSizeChange={() => flatListRef.current?.scrollToEnd({ animated: true })}
          onLayout={() => flatListRef.current?.scrollToEnd({ animated: true })}
        />

        <View style={styles.inputContainer}>
          <View style={styles.inputWrapper}>
            <TextInput
              style={styles.input}
              placeholder="Type your message..."
              placeholderTextColor="#94A3B8"
              value={inputText}
              onChangeText={setInputText}
              multiline
            />
            <TouchableOpacity 
              style={[styles.sendButton, !inputText.trim() && styles.sendButtonDisabled]} 
              onPress={sendMessage}
              disabled={!inputText.trim()}
            >
              <LinearGradient
                colors={inputText.trim() ? ['#3B82F6', '#1D4ED8'] : ['#E2E8F0', '#E2E8F0']}
                style={styles.sendButtonGradient}
                start={{ x: 0, y: 0 }}
                end={{ x: 1, y: 1 }}
              >
                <Ionicons name="send" size={16} color={inputText.trim() ? "#FFFFFF" : "#94A3B8"} />
              </LinearGradient>
            </TouchableOpacity>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F8FAFC',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 20,
    paddingVertical: 16,
    backgroundColor: '#FFFFFF',
    borderBottomWidth: 1,
    borderBottomColor: '#F1F5F9',
  },
  headerTitleContainer: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  headerTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#0F172A',
    marginLeft: 8,
  },
  headerButton: {
    padding: 4,
  },
  keyboardAvoid: {
    flex: 1,
  },
  messageList: {
    paddingHorizontal: 16,
    paddingTop: 24,
    paddingBottom: 24,
  },
  messageBubble: {
    flexDirection: 'row',
    marginBottom: 16,
    maxWidth: '85%',
  },
  userBubble: {
    alignSelf: 'flex-end',
  },
  botBubble: {
    alignSelf: 'flex-start',
  },
  botAvatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: '#3B82F6',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
    marginTop: 4,
  },
  messageContent: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderRadius: 20,
  },
  userMessageContent: {
    backgroundColor: '#3B82F6',
    borderBottomRightRadius: 4,
  },
  botMessageContent: {
    backgroundColor: '#FFFFFF',
    borderBottomLeftRadius: 4,
    borderWidth: 1,
    borderColor: '#E2E8F0',
  },
  messageText: {
    fontSize: 16,
    lineHeight: 24,
  },
  userMessageText: {
    color: '#FFFFFF',
  },
  botMessageText: {
    color: '#334155',
  },
  inputContainer: {
    paddingHorizontal: 16,
    paddingVertical: 12,
    backgroundColor: '#FFFFFF',
    borderTopWidth: 1,
    borderTopColor: '#F1F5F9',
  },
  inputWrapper: {
    flexDirection: 'row',
    alignItems: 'flex-end',
    backgroundColor: '#F8FAFC',
    borderRadius: 24,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    paddingHorizontal: 16,
    paddingVertical: 8,
  },
  input: {
    flex: 1,
    maxHeight: 120,
    fontSize: 16,
    color: '#1E293B',
    paddingTop: 8,
    paddingBottom: 8,
  },
  sendButton: {
    marginLeft: 12,
    marginBottom: 4,
  },
  sendButtonDisabled: {
    opacity: 0.7,
  },
  sendButtonGradient: {
    width: 36,
    height: 36,
    borderRadius: 18,
    justifyContent: 'center',
    alignItems: 'center',
    paddingLeft: 2, 
  },
});

const markdownStyles = {
  body: {
    color: '#334155',
    fontSize: 16,
    lineHeight: 24,
  },
  paragraph: {
    marginTop: 0,
    marginBottom: 8,
  },
  strong: {
    fontWeight: 'bold',
    color: '#0F172A',
  },
  em: {
    fontStyle: 'italic',
  },
  heading1: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#0F172A',
    marginVertical: 8,
  },
  heading2: {
    fontSize: 20,
    fontWeight: 'bold',
    color: '#0F172A',
    marginVertical: 8,
  },
  heading3: {
    fontSize: 18,
    fontWeight: 'bold',
    color: '#0F172A',
    marginVertical: 8,
  },
  link: {
    color: '#3B82F6',
    textDecorationLine: 'underline',
  },
  list_item: {
    marginBottom: 4,
  },
  code_inline: {
    backgroundColor: '#F1F5F9',
    color: '#EF4444',
    paddingHorizontal: 4,
    borderRadius: 4,
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
  },
  code_block: {
    backgroundColor: '#F8FAFC',
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#E2E8F0',
    fontFamily: Platform.OS === 'ios' ? 'Menlo' : 'monospace',
    color: '#334155',
    marginVertical: 8,
  },
};
